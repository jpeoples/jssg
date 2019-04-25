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
    {% for page in pages %}
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
    def __init__(self, env, base_render_context=None, jit_context=None):
        self.env = env
        self.base_render_context=base_render_context if base_render_context is not None else {}
        self.jit_context = jit_context if jit_context is not None else []


    def __call__(self, inpath, outpath):
        jenv = self.env['jinja']['jenv']
        render_ctx = self.base_render_context.copy()
        for jit in self.jit_context:
            new_ctx = jit(self.env, render_ctx, inpath, outpath)
            render_ctx.update(new_ctx)

        contents = inpath.open('r', encoding='utf-8').read()
        jt = jenv.from_string(contents)
        with outpath.open('w', encoding='utf-8') as f:
            f.write(jt.render(render_ctx))

    def add_jit_context(self, f, *args, **kwargs):
        kwargs = kwargs if kwargs is not None else {}
        return JinjaFileNew(self.env, self.base_render_context,
                self.jit_context + [lambda e,r,i,o: f(e,r,i,o,*args,**kwargs)])

    def add_context(self, ctx):
        new_ctx = self.base_render_context.copy()
        new_ctx.update(ctx)
        return JinjaFileNew(self.env, new_ctx, self.jit_context)



#### Other Rule Procs
def ignore_file(*args, **kwargs):
    """RuleProc function doing nothing at all!"""
    pass


def push_page(pages,page,additional_ctx=None):
    if additional_ctx is not None:
        page = page.copy()
        page.update(additional_ctx)

    pages.append(page)

def sort_pages(pages, key='date'):
    return sorted(pages, key=lambda x: x[key], reverse=True)



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

class Builtins:
    def requires(self):
        return ()

    def setup(self, conf, env):
        env['input_directory'] = pathlib.Path(conf['input_directory'])
        env['output_directory'] = pathlib.Path(conf['output_directory'])

        return {
            "rule_procs": {
                "ignore": ignore_file,
                "copy": (mirror, copy_file),
            },
            "path_maps": {
                "mirror": mirror,
                "to_html": to_html,
                "remove_internal_extensions": remove_internal_extensions,
                "replace_extensions": replace_extensions
            },
            "file_maps": {
                "copy": copy_file
            }
        }

class JinjaPlug:
    def requires(self):
        return ("builtin",)
    def setup(self, conf, env):
        jconf = conf['jinja']
        if jconf.get('jenv') is not None:
            env['jinja'] = {'jenv': jenv}
        else:
            env['jinja'] = {
                'jenv': jinja_env(
                    load_paths_with_prefix=jconf.get('load_paths_with_prefix', ()),
                    load_paths=jconf.get('load_paths', ()),
                    additional_filters=jconf.get('additional_filters')
                )
            }

        jinja_file = JinjaFile(env, jconf.get('base_render_context', {}),
                jconf.get('jit_context', []))

        return {
            "file_maps": {
                "jinja": jinja_file
            }
        }

class MarkdownFilter:
    def requires(self):
        return ("jinja",)

    def setup(self, conf, env):
        mconf = conf.get(markdown_filter)

        if mconf is not None:
            jconf = env['jinja']
            mdfilter = markdown_filter(mconf.get('extensions'), mconf.get('extension_configs'))
            jenv = jconf['jenv']
            jenv.filters.update({"markdown_filter": mdfilter})

class DateFilters:
    def requires(self):
        return ("builtin",)

    def setup(self, conf, env):
        dconf = conf.get('date_filters')
        if dconf is not None:
            date_format_string=dconf.get('date_format_string', '%B %d, %Y')
            jconf = env['jinja']
            jenv = jconf['jenv']
            jenv.filters.update(date_filters(date_format_string))


def default_plugs():
    return {
            "builtin": Builtins(),
            "jinja": JinjaPlug(),
            "markdown_filter": MarkdownFilter(),
            "date_filters": DateFilters()
        }


class Struct:
    def add_dict(self, dct):
        if dct is not None: self.__dict__.update(dct)

class Environment:
    def __init__(self, conf, plugs=default_plugs()):

        self.rule = Struct()
        self.path = Struct()
        self.file = Struct()

        initted = set()
        env = {}
        for name,plug in plugs.items():
            self._init_plug(name,plug,plugs,initted,conf,env)

        self.env = env


    def _init_plug(self, name, plug, plugs, initted, conf, env):
        for dep in plug.requires():
            if not dep in initted:
                self._init_plug(dep, plugs[dep], plugs, initted,conf,env)

        outputs = plug.setup(conf, env)
        if outputs is not None:
            self.rule.add_dict(outputs.get('rule_procs'))
            self.file.add_dict(outputs.get('file_maps'))
            self.path.add_dict(outputs.get('path_maps'))
        initted.add(name)

    def build_dir(self, rules, subdir=None):
        directory = self.env['input_directory']

        if subdir is not None:
            directory = directory / subdir

        for fn in walk_directory(directory, self.env['input_directory']):
            rule = get_first_matching_rule_proc(rules, fn)
            self.build(rule, fn)

    def build(self, rule, fn):
        f = self._get_callable_rule(rule)
        return f(fn)

    def _get_callable_rule(self, rule):
        """Convert a (PathMap,FileMap) pair into a callable RuleProc

        If rule is already a callable, do nothing.
        """
        if not callable(rule):
            def f(fn):
                outfn = rule[0](fn)
                inp, outp = self.env['input_directory'] / fn, self.env['output_directory'] / outfn
                ensure_directory(outp)
                rule[1](inp, outp)
            return f
        return rule

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
