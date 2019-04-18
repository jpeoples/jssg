# Std libs
import sys
import os
import shutil
from dateutil.parser import parse as parse_date
from email.utils import format_datetime as rss_date
import pathlib
import bisect
import fnmatch

#requirements
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

def walk_directory(input_directory):
    for directory_path, _, file_names in os.walk(str(input_directory)):
        relative_directory = pathlib.Path(directory_path).relative_to(input_directory)
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

# Provide the default file mapping operations.
class DefaultPathMaps:
    def __init__(self, indir, outdir):
        self.indir = pathlib.Path(indir)
        self.outdir = pathlib.Path(outdir)

    def mirror(self, fn):
        return self.indir / fn, self.outdir / fn

    def to_html(self, fn):
        return self.indir / fn, self.outdir / path_replace_all_suffix(fn, '.html')

    def remove_internal_extensions(self, fn):
        return self.indir / fn, self.outdir / path_replace_all_suffix(fn, fn.suffix)


class DefaultFileMaps:
    def __init__(self, jenv, render_context):
        self.jenv = jenv
        self.render_context = render_context


    def copy_file(self, inpath, outpath)
        shutil.copy(str(inpath), str(outpath))

    def ignore_file(self, inpath, outpath):
        pass

    def jinja_file(self, inpath, outpath):
        contents = inpath.open('r').read()
        jt = jenv.from_string(contents)
        with outpath.open('w', encoding='utf-8') as f:
            f.write(jt.render(self.render_context))



class PageCollection:
    """A class for storing information about a set of pages"""
    def __init__(self, sort_key):
        self.pages = []
        self.keys = []
        self.sort_key = sort_key

    def post_push(self, post):
        key = post[self.sort_key]
        x = bisect.bisect_left(self.keys, key)

        self.keys.insert(x, key)
        self.pages.insert(x, post)

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
        return self.history(count=len(self.posts))

def get_callable_rule(rule):
    if not callable(rule):
        def f(fn):
            inp, outp = rule[0](fn)
            ensure_directory(outp)
            rule[1](inpath, outpath)
        return f
    return rule


class BuildRules:
    def __init__(self, rules):
        self.rules = rules

    def match(self, fn):
        # call first matching rule
        for matcher, rule in self.rules:
            if self._single_match(matcher, fn):
                func = get_callable_rule(rule)
                return func(fn)

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
            ret = fnmatch.fnmatch(fpath, matcher)
        return ret



def jinja_env(load_paths, additional_filters=None):
    user_loader = jinja2.ChoiceLoader([jinja2.FileSystemLoader(path) for path in load_paths])
    builtin_loader = jinja2.DictLoader({'rss_base.xml': rss_base_src})

    loader = jinja2.PrefixLoader({
        'user': user_loader,
        'builtin': builtin_loader
        })
    jinja_env = jinja2.Environment(loader=loader)
    if additional_filters is not None:
        jinja_env.filters.update(additional_filters)

    return jinja_env



class Environment:
    def __init__(self, indir, outdir, *, template_loader_dirs=None, mdext=None, mdextconf=None, jenv=None, date_format_str='%B %d, %Y', template_render_data=None):
        if isinstance(indir, str):
            indir = path.Path(indir)
        if isinstance(outdir, str):
            outdir = path.Path(outdir)

        self.indir = indir
        self.outdir = outdir


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
            'parse_date': parse_date,
            'format_date': lambda x: x.strftime(date_format_str),
            'rss_format_date': rss_date })

        self.jenv = jenv

        if template_render_data is None:
            template_render_data = {}


    def build_dir(self, rules, subdir=None, additional_template_render_data=None):
        if additional_template_render_data is not None:
            template_render_data = self.template_render_data.copy().update(additional_template_render_data)
        else:
            template_render_data = self.template_render_data


        self.path_maps = DefaultPathMaps(indir, outdir)
        self.file_maps = DefaultFileMaps(jenv, template_render_data)

        if not isinstance(rules, BuildRules):
            rules = BuildRules(rules)

        directory = self.indir
        if subdir is not None:
            directory = directory / subdir

        for fn in walk_directory(directory):
            rules.match(fn)

