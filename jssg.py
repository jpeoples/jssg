"""jssg -- Jake's Static Site Generation Library

This is a simple module for aiding with static site generation. The
basic concept is to allow the generation of a static html website by
transforming a source directory into a build directory.
"""

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

rss_base_src = """
<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
    <title>{{rss_title}}</title>
    <link>{{rss_home_page}}</link>
    <atom:link href="{{rss_link}}" rel="self" type="application/rss+xml" />
    <description>{{rss_description}}</description>
    {% for page in pages | reverse %}
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
""".strip()

def walk_directory(input_directory, relative_to=None):
    """A generator returning all files under input_directory

    This function returns all functions, recursively, under input_directory,
    expressed as a path relative to relative_to. If relative_to is None,
    then input_directory is used as relative_to.
    """
    if relative_to is None:
        relative_to = input_directory
    for directory_path, _, file_names in os.walk(str(input_directory)):
        relative_directory = pathlib.Path(directory_path).relative_to(relative_to)
        for fn in file_names:
            yield relative_directory.joinpath(fn)

# Path utility functions
def ensure_directory(path):
    """Ensure the parent directory to path exists"""
    try:
        path.parent.mkdir(parents=True)
    except FileExistsError:
        pass

def path_replace_all_suffix(path, suffix):
    """Replace all extensions with a single new extension"""
    while path.suffix:
        path = path.with_suffix('')
    return path.with_suffix(suffix)


#### PathMap functions
def mirror(fn):
    return fn

def remove_internal_extensions(fn):
    return path_replace_all_suffix(fn, fn.suffix)

def to_html(fn):
    return path_replace_all_suffix(fn, '.html')

def replace_extensions(new_ext):
    return lambda fn: path_replace_all_suffix(fn, '.'+new_ext)


#### FileMap Functions
def copy_file(inpath, outpath):
    """FileMap function copying a file directly"""
    shutil.copy(str(inpath), str(outpath))

class JinjaFile:
    def __init__(self, jenv, base_url, outdir, page_collection=None, render_ctx=None):
        if render_ctx is None:
            render_ctx = {}
        self.jenv = jenv
        self.base_url = base_url
        self.outdir = outdir
        self.page_collection = page_collection
        self.render_ctx = render_ctx

    def override(self, page_collection=None, additional_ctx=None):
        if additional_ctx is not None:
            render_ctx = self.render_ctx.copy()
            render_ctx.update(additional_ctx)
        else:
            render_ctx = self.render_ctx

        if page_collection is None:
            page_collection = self.page_collection

        return JinjaFile(self.jenv, self.base_url, self.outdir, page_collection, render_ctx)

    def __call__(self, inpath, outpath):
        href = outpath.relative_to(self.outdir).as_posix()
        additional_ctx = {
                'href': href,
                'fullhref': self.base_url + href
        }

        render_context = self.render_ctx.copy()
        render_context.update(additional_ctx)
        if self.page_collection is not None:
            render_context['push_to_collection'] = lambda x: push_page(self.page_collection, x, additional_ctx)

        contents = inpath.open('r', encoding='utf-8').read()
        jt = self.jenv.from_string(contents)
        with outpath.open('w', encoding='utf-8') as f:
            f.write(jt.render(render_context))



#### Other Rule Procs
def ignore_file(*args, **kwargs):
    """RuleProc function doing nothing at all!"""
    pass


def push_page(pages,page,additional_ctx=None):
    if additional_ctx is not None:
        page = page.copy()
        page.update(additional_ctx)

    pages.append(page)

def by_year(pages):
    current_year = None
    for post in reversed(pages):
        date = post['date']
        if date.year != current_year:
            if current_year is not None:
                yield obj
            obj = {'year': date.year, 'posts': []}
            current_year = date.year

        obj['posts'].append(post)
    yield obj

def sort_pages(pages, key='date'):
    return sorted(pages, key=lambda x: x[key])



def get_first_matching_rule_proc(rules, fn):
    """Find the first matching rule_proc on fn"""
    for matcher, rule in rules:
        if _single_match(matcher, fn):
            return rule

def _single_match(matcher, fn):
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
            # NOTE: we can group glob strings for convenience
            for match in matcher:
                ret = fnmatch.fnmatch(fpath, match)
                if ret:
                    break
    return ret

class RuleEnv:
    def __init__(self, indir, outdir):
        if isinstance(indir, str):
            indir = pathlib.Path(indir)
        if isinstance(outdir, str):
            outdir = pathlib.Path(outdir)

        self.indir = indir
        self.outdir = outdir

    def build_dir(self, rules, subdir=None):
        directory = self.indir
        if subdir is not None:
            directory = directory / subdir

        for fn in walk_directory(directory, self.indir):
            rule = get_first_matching_rule_proc(rules, fn)
            self.apply_rule_proc(rule, fn)

    def get_callable_rule(self, rule):
        """Convert a (PathMap,FileMap) pair into a callable RuleProc

        If rule is already a callable, do nothing.
        """
        if not callable(rule):
            def f(fn):
                outfn = rule[0](fn)
                inp, outp = self.indir / fn, self.outdir / outfn
                ensure_directory(outp)
                rule[1](inp, outp)
            return f
        return rule

    def apply_rule_proc(self, rule_proc, fn):
        """Apply a RuleProc to a fn with ctx.

        This works for callable rule_proc's and tuples of (path_map, file_map)
        """
        f = self.get_callable_rule(rule_proc)
        return f(fn)

#### Jinja setup helpers
def jinja_env(load_paths=(), load_paths_with_prefix=(), additional_filters=None):
    """Initialize a jinja env that searches all load_paths for templates.

    builtin templates can also be found under builtin/

    load_paths is an iterable containing either strings to paths to search,
    or tuples containing (prefix, path) pairs.
    """
    import jinja2
    user_prefix_loader = jinja2.PrefixLoader(
            {prefix: jinja2.FileSystemLoader(path)
                for path, prefix in load_paths_with_prefix})

    user_loader = jinja2.ChoiceLoader([jinja2.FileSystemLoader(path) for path in load_paths])

    builtin_loader = jinja2.PrefixLoader({
        'builtin': jinja2.DictLoader({'rss_base.xml': rss_base_src})
    })

    loader = jinja2.ChoiceLoader([user_loader, user_prefix_loader, builtin_loader])

    jinja_env = jinja2.Environment(loader=loader, undefined=jinja2.StrictUndefined)
    if additional_filters is not None:
        jinja_env.filters.update(additional_filters)
    else:
        jinja_env.filters.update(date_filters())
        jinja_env.filters['markdown'] = markdown_filter()
        jinja_env.filters['pages_by_year'] = by_year

    return jinja_env

def date_filters(date_format_str='%B %d, %Y'):
    return {
        'parse_date': dateutil.parser.parse,
        'format_date': lambda x: format_date(x, date_format_str),
        'rss_format_date': rss_date
    }


def markdown_filter(extensions=None, extension_configs=None):
    import markdown
    default_extensions = [
        'markdown.extensions.extra',
        'markdown.extensions.admonition',
        'markdown.extensions.toc',
        'markdown.extensions.codehilite',
        'mdx_math'
    ]
    default_extension_configs = {
            "mdx_math": {'enable_dollar_delimiter': True}
    }

    if extensions is None:
        extensions = default_extensions

    if extension_configs is None:
        extension_configs = default_extension_configs

    mdfilter = lambda x: markdown.markdown(x, extensions=extensions, extension_configs=extension_configs)
    return mdfilter

def format_date(x, format_str):
    """Format a datestr with a given format string"""
    if isinstance(x, str):
        x = dateutil.parser.parse(x)
    return x.strftime(format_str)

def rss_date(x):
    """Format a datestr into a format acceptable for RSS"""
    if isinstance(x, str):
        x = dateutil.parser.parse(x)
    return email.utils.format_datetime(x)
