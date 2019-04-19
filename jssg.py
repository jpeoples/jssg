# Std libs
import sys
import os
import shutil
import email.utils
import pathlib
import bisect
import fnmatch

#requirements
import dateutil.parser
import jinja2
import markdown

rss_base_src = """
<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
    <title>{{rss_title}}</title>
    <link>{{rss_home_page}}</link>
    <atom:link href="{{rss_link}}" rel="self" type="application/rss+xml" />
    <description>{{rss_description}}</description>
    {% for page in pages.all_pages() %}
    <item>
        <title>{{page.title | e}}</title>
        <link>{{page.fullhref}}</link>
        <guid isPermaLink="true">{{page.fullhref}}</guid>
        <pubDate>{{page.date | rss_format_date}}</pubDate>
        <description>{{page.content | e}}</description>
    </item>
    {% endfor %}
</channel>
</rss>
"""


def walk_directory(input_directory, relative_to=None):
    if relative_to is None:
        relative_to = input_directory
    for directory_path, _, file_names in os.walk(str(input_directory)):
        relative_directory = pathlib.Path(directory_path).relative_to(relative_to)
        for fn in file_names:
            yield relative_directory.joinpath(fn)

# Path utility functions
def ensure_directory(path):
    try:
        path.parent.mkdir(parents=True)
    except FileExistsError:
        pass

def path_replace_all_suffix(path, suffix):
    """Replace all extensions with a single new extension"""
    while path.suffix:
        path = path.with_suffix('')
    return path.with_suffix(suffix)


def mirror(ctx, fn):
    return ctx['indir'] / fn, ctx['outdir'] / fn

def to_html(ctx, fn):
    return ctx['indir'] / fn, ctx['outdir'] / path_replace_all_suffix(fn, '.html')

def remove_internal_extensions(ctx, fn):
    return ctx['indir'] / fn, ctx['outdir'] / path_replace_all_suffix(fn, fn.suffix)


def copy_file(ctx, inpath, outpath):
    shutil.copy(str(inpath), str(outpath))

def jinja_file(ctx, inpath, outpath):
    jenv = ctx['jenv']
    render_context = ctx['render_context']
    page_collection = ctx['page_collection']
    base_url = ctx['base_url']
    outdir = ctx['outdir']

    href = outpath.relative_to(outdir).as_posix()
    additional_ctx = {
            'href': href,
            'fullhref': base_url + href
            }


    if page_collection is not None:
        render_context = render_context.copy()
        render_context['push_to_collection'] = lambda x: page_collection.push(x, additional_ctx)
        render_context.update(additional_ctx)

    contents = inpath.open('r').read()
    jt = jenv.from_string(contents)
    with outpath.open('w', encoding='utf-8') as f:
        f.write(jt.render(render_context))

def ignore_file(*args, **kwargs):
    pass


class PageCollection:
    """A class for storing information about a set of pages"""
    def __init__(self, sort_key='date'):
        self.pages = []
        self.keys = []
        self.sort_key = sort_key

    def push(self, page_dict, additional_ctx=None):
        if additional_ctx is not None:
            page_dict = page_dict.copy()
            page_dict.update(additional_ctx)

        key = page_dict[self.sort_key]
        x = bisect.bisect_left(self.keys, key)

        self.keys.insert(x, key)
        self.pages.insert(x, page_dict)

    def history(self, count=20):
        for i, post in enumerate(reversed(self.pages)):
            if count is not None and i >= count:
                break
            yield post

    def by_year(self):
        current_year = None
        for post in reversed(self.pages):
            date = post['date']
            if date.year != current_year:
                if current_year is not None:
                    yield obj
                obj = {'year': date.year, 'posts': []}
                current_year = date.year

            obj['posts'].append(post)
        yield obj

    def all_pages(self):
        return self.history(count=len(self.pages))

def enable_push_to_collection(pages, env=None):
    if env is None:
        env = {}
    env.copy()
    env.update({'push_to_collection': pages.push})
    return env

def get_callable_rule(rule):
    if not callable(rule):
        def f(ctx, fn):
            inp, outp = rule[0](ctx, fn)
            ensure_directory(outp)
            rule[1](ctx, inp, outp)
        return f
    return rule


class BuildRules:
    def __init__(self, rules):
        self.rules = rules

    def match(self, ctx, fn):
        # call first matching rule
        for matcher, rule in self.rules:
            if self._single_match(matcher, fn):
                func = get_callable_rule(rule)
                return func(ctx, fn)

    def _single_match(self, matcher, fn):
        try:
            ret = matcher(fn)
        except TypeError:
            # fallback is to match as glob string
            # NOTE: One would think we could just use fn.match(matcher)
            # here, and indeed, that is what we used to do. However, for
            # some reason this was often failing on Windows... So I have
            # replaced it with the fnmatch version, which actually seems
            # to work for now.
            fpath = fn.as_posix()
            if isinstance(matcher, str):
                ret = fnmatch.fnmatch(fpath, matcher)
            else:
                for match in matcher:
                    ret = fnmatch.fnmatch(fpath, match)
                    if ret:
                        break
        return ret



def jinja_env(load_paths, additional_filters=None):
    user_loader = jinja2.ChoiceLoader([jinja2.FileSystemLoader(path) for path in load_paths])
    builtin_loader = jinja2.DictLoader({'rss_base.xml': rss_base_src})

    builtin_loader = jinja2.PrefixLoader({
        'builtin': builtin_loader
        })

    loader = jinja2.ChoiceLoader([user_loader,builtin_loader])
    jinja_env = jinja2.Environment(loader=loader, undefined=jinja2.StrictUndefined)
    if additional_filters is not None:
        jinja_env.filters.update(additional_filters)

    return jinja_env


def format_date(x, format_str):
    if isinstance(x, str):
        x = dateutil.parser.parse(x)
    return x.strftime(format_str)

def rss_date(x):
    if isinstance(x, str):
        x = dateutil.parser.parse(x)
    return email.utils.format_datetime(x)


class Environment:
    def __init__(self, indir, outdir, base_url, *, template_loader_dirs=None, mdext=None, mdextconf=None, jenv=None, date_format_str='%B %d, %Y', template_render_data=None):
        if isinstance(indir, str):
            indir = pathlib.Path(indir)
        if isinstance(outdir, str):
            outdir = pathlib.Path(outdir)

        self.indir = indir
        self.outdir = outdir
        self.base_url = base_url


        # Set up the markdown filter (set up extensions, then grab the
        # markdown object)
        if mdextconf is None:
            mdextconf = {}

        if mdext is None:
            mdext = [
                'markdown.extensions.extra',
                'markdown.extensions.admonition',
                'markdown.extensions.toc',
                'markdown.extensions.codehilite',
                'mdx_math'
            ]
            mdextconf.update({"mdx_math": {'enable_dollar_delimiter': True}})

        mdfilter = markdown.Markdown(extensions=mdext, extension_configs=mdextconf).convert

        # set up the jinja env
        if jenv is None:
            if template_loader_dirs is None:
                template_loader_dirs = (str(indir),)
            jenv = jinja_env(template_loader_dirs)

        # add default filters to jinja env
        jenv.filters.update({
            'markdown': mdfilter,
            'parse_date': dateutil.parser.parse,
            'format_date': lambda x: format_date(x, date_format_str),
            'rss_format_date': rss_date })

        self.jenv = jenv

        if template_render_data is None:
            template_render_data = {}
        self.template_render_data = template_render_data
        self.template_render_data['base_url'] = base_url


    def build_dir(self, rules, subdir=None, additional_template_render_data=None, page_collection=None):
        if additional_template_render_data is not None:
            template_render_data = self.template_render_data.copy()
            template_render_data.update(additional_template_render_data)
        else:
            template_render_data = self.template_render_data

        ctx = {'indir': self.indir, 'outdir': self.outdir, 'base_url': self.base_url,
               'jenv': self.jenv, 'render_context': template_render_data,
               'page_collection': page_collection}

        if not isinstance(rules, BuildRules):
            rules = BuildRules(rules)

        directory = self.indir
        if subdir is not None:
            directory = directory / subdir

        for fn in walk_directory(directory, self.indir):
            rules.match(ctx, fn)
