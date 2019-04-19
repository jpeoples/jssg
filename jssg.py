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


def mirror(ctx, fn):
    """PathMap function mirroring a path in source dir to build dir"""
    return ctx['indir'] / fn, ctx['outdir'] / fn

def to_html(ctx, fn):
    """PathMap function mirroring a source dir path, replacing all extensions with .html"""
    return ctx['indir'] / fn, ctx['outdir'] / path_replace_all_suffix(fn, '.html')

def remove_internal_extensions(ctx, fn):
    """PathMap function mirroring a source dir path, removing all extensions but the last"""
    return ctx['indir'] / fn, ctx['outdir'] / path_replace_all_suffix(fn, fn.suffix)


def copy_file(ctx, inpath, outpath):
    """FileMap function copying a file directly"""
    shutil.copy(str(inpath), str(outpath))

def jinja_file(ctx, inpath, outpath):
    """FileMap function rendering the input file as a jinja2 template to produce the output file.

    In addition to providing any user supplied tempalte_render_data (via
    the Environment constructor, or build_all method) in the render dictionary,
    'href' and 'fullhref' will also be passed, containing the url relative
    to the base of website, and full url, respectively. Further, 'push_to_collection'
    will be provided as a function, allowing metadata to be pushed to the
    current page collection (if any).
    """
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

    render_context = render_context.copy()
    render_context.update(additional_ctx)
    if page_collection is not None:
        render_context['push_to_collection'] = lambda x: page_collection.push(x, additional_ctx)

    contents = inpath.open('r', encoding='utf-8').read()
    jt = jenv.from_string(contents)
    with outpath.open('w', encoding='utf-8') as f:
        f.write(jt.render(render_context))

def ignore_file(*args, **kwargs):
    """RuleProc function doing nothing at all!"""
    pass


class PageCollection:
    """A class for storing information about a sorted collection of pages.

    Importantly, when building with Environment.build_dir, if a post_collection
    is specified, then the push method is made available to jinja templates
    as "push_to_collection" (taking one argument, page_dict. additional_ctx
    is provided by jinja_file).

    In this way, sets of files can be built, storing any desired metadata,
    and then this metadata can be made available to other templates later.
    This allows automated creation of archives, for example.
    """
    def __init__(self, sort_key='date'):
        self.pages = []
        self.keys = []
        self.sort_key = sort_key

    def push(self, page_dict, additional_ctx=None):
        """Add a page to collection, maintaining sort on self.sort_key"""
        if additional_ctx is not None:
            page_dict = page_dict.copy()
            page_dict.update(additional_ctx)

        key = page_dict[self.sort_key]
        x = bisect.bisect_left(self.keys, key)

        self.keys.insert(x, key)
        self.pages.insert(x, page_dict)

    def history(self, count=20):
        """Get the last count pages in collection, in reverse order"""
        for i, post in enumerate(reversed(self.pages)):
            if count is not None and i >= count:
                break
            yield post

    def by_year(self):
        """Get pages grouped by year, in reverse chronological order"""
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
        """Get all pages in reverse chronological order"""
        return self.history(count=len(self.pages))


def get_callable_rule(rule):
    """Convert a (PathMap,FileMap) pair into a callable RuleProc

    If rule is already a callable, do nothing.
    """
    if not callable(rule):
        def f(ctx, fn):
            inp, outp = rule[0](ctx, fn)
            ensure_directory(outp)
            rule[1](ctx, inp, outp)
        return f
    return rule


class BuildRules:
    """A class to apply build rules to incoming files."""
    def __init__(self, rules):
        self.rules = rules

    def match(self, ctx, fn):
        """Call the first matching build rule on fn, supplying ctx"""
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
                # NOTE: we can group glob strings for convenience
                for match in matcher:
                    ret = fnmatch.fnmatch(fpath, match)
                    if ret:
                        break
        return ret



def jinja_env(load_paths, additional_filters=None):
    """Initialize a jinja env that searches all load_paths for templates.

    builtin templates can also be found under builtin/
    """
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
    """Format a datestr with a given format string"""
    if isinstance(x, str):
        x = dateutil.parser.parse(x)
    return x.strftime(format_str)

def rss_date(x):
    """Format a datestr into a format acceptable for RSS"""
    if isinstance(x, str):
        x = dateutil.parser.parse(x)
    return email.utils.format_datetime(x)


class Environment:
    """The main class provided for building directories.

    indir and outdir are the source and build directories, and base_url
    is the complete url of the website.

    template_loader_dirs:
        directories to be searched for jinja templates. In particular,
        if a template refers to another template (such as via "extends"),
        then these are the directories that will be searched. If None,
        indir will be used.
    mdext:
        extensions to use in the markdown.Markdown class for processing
        text through the markdown filter in a jinja template.
    mdextconf:
        The extension configuration dict (extension_configs) to be passed
        to the markdown.Markdown class for use in the markdown filter.
    additional_jinja_filters:
        Additional filter functions to be made available in Jinja templates.
    date_format_str:
        The format string to use in the format_date filter.
    template_render_data:
        Context to be provided when rendering Jinja templates.
    """
    def __init__(self, indir, outdir, base_url, *, template_loader_dirs=None, mdext=None, mdextconf=None, additional_jinja_filters=None, date_format_str='%B %d, %Y', template_render_data=None, user_ctx=None):
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

        mdfilter = lambda x: markdown.markdown(x, extensions=mdext, extension_configs=mdextconf)

        # set up the jinja env
        if template_loader_dirs is None:
            template_loader_dirs = (str(indir),)
        jenv = jinja_env(template_loader_dirs, additional_jinja_filters)

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

        if user_ctx is None:
            self.user_ctx = {}
        else:
            self.user_ctx = user_ctx


    def build_dir(self, rules, subdir=None, additional_template_render_data=None, page_collection=None, additional_user_ctx=None):
        """Apply build rules to all files recursively in a directory.

        rules:
            A list of build rules, or a BuildRules object.
        subdir:
            If given, subdir must be a child of source dir. In this case, only
            files under subdir are processed. If none, the entire source
            dir is processed.
        additional_template_render_data:
            Additional data to add to the render context dictionary for jinja templates.
        page_collection:
            A PageCollection object. If active, it's push method will be
            made available to jinja templates as "push_to_collection", where
            the second argument 'additional_ctx' will be passed in automatically
            containing 'href' and 'fullhref', the url relative to the website,
            and complete url respectively.
        """
        if additional_template_render_data is not None:
            template_render_data = self.template_render_data.copy()
            template_render_data.update(additional_template_render_data)
        else:
            template_render_data = self.template_render_data

        ctx = self.user_ctx.copy()
        if additional_user_ctx:
            ctx.update(additional_user_ctx)
        ctx.update({'indir': self.indir, 'outdir': self.outdir, 'base_url': self.base_url,
               'jenv': self.jenv, 'render_context': template_render_data,
               'page_collection': page_collection})
        

        if not isinstance(rules, BuildRules):
            rules = BuildRules(rules)

        directory = self.indir
        if subdir is not None:
            directory = directory / subdir

        for fn in walk_directory(directory, self.indir):
            rules.match(ctx, fn)
