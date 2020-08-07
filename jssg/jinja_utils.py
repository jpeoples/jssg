from .execution_rule import ExecutionRule

import dateutil.parser
import email.utils

class JinjaRenderable(ExecutionRule):
    def __init__(self, jf):
        self.jf = jf

    @property
    def env(self):
        return self.jf.env

    @property
    def ctx(self):
        return self.jf.ctx

    def __call__(self, fs, inf, outf):
        ctx = self.jf.immediate_context(fs, inf, outf)
        template = self.load_file(fs, inf, outf, ctx)
        execution = lambda state: fs.write(outf,
                template.render(ctx, user_context=state))
        state = dict(type="jinja_template", context=ctx)
        return execution, state

    def load_file(self, fs, inf, outf, ctx):
        raise NotImplementedError

class JinjaDataFile(JinjaRenderable):
    def load_file(self, fs, inf, outf, ctx):
        s = fs.read(inf)
        t = self.env.from_string(s)
        tmod = t.make_module(ctx)
        layout = self.env.get_template(tmod.content_layout)
        ctx['data_template'] = tmod
        return layout

class JinjaLayoutFile(JinjaRenderable):
    def load_file(self, fs, inf, outf, ctx):
        # Simply read the file, and make it a template
        s = fs.read(inf)
        t = self.env.from_string(s)
        return t



class JinjaFile(ExecutionRule):
    def __init__(self, env, ctx):
        self.env = env
        self.ctx = ctx
        self.hooks = []

    def add_immediate_context_hook(self, hook):
        self.hooks.append(hook)

    def immediate_context(self, fs, inf, outf):
        ctx = self.ctx.copy()
        if len(self.hooks) > 0:
            for hook in self.hooks:
                ctx.update(hook(self.ctx, inf, outf))
        return ctx


    @property
    def as_layout(self):
        return JinjaLayoutFile(self)

    def __call__(self, fs, inf, outf):
        return JinjaDataFile(self)(fs, inf, outf)



#### Jinja setup helpers
def jinja_env(search_paths=(), prefix_paths=(), additional_loaders=None, filters=None):
    """Initialize a jinja env that searches all load_paths for templates.

    builtin templates can also be found under builtin/

    search_paths are paths to search for template files. These paths will be
    searched under, in order, when a template load (e.g. extends) is found.

    prefix_paths will be searched, but must include the directory as a prefix.
    For example if 'layouts' is in prefix_paths, and contains template 'a', then
    to be found, you must use the name 'layouts/a'. To use a prefix other than the
    full directory path, use a tuple (path, prefix). Continuing the example,
    if ('layouts', 'x') is is prefix_paths, then the template is found via 'x/a'.
    """
    import jinja2

    def normalize_prefix_paths(p):
        for tup in p:
            try:
                path, prefix = tup
                yield (path, prefix)
            except ValueError:
                # Cannot be unpacked!
                assert isinstance(tup, str)
                yield (tup, tup)


    user_prefix_loader = jinja2.PrefixLoader(
            {prefix: jinja2.FileSystemLoader(path)
                for path, prefix in normalize_prefix_paths(prefix_paths)})

    user_loader = jinja2.ChoiceLoader([jinja2.FileSystemLoader(path) for path in search_paths])

    if additional_loaders is not None:
        additional_loader = jinja2.ChoiceLoader(additional_loaders)

    loader = jinja2.ChoiceLoader([user_loader, user_prefix_loader, additional_loader])

    jinja_env = jinja2.Environment(loader=loader, undefined=jinja2.StrictUndefined)
    if filters is not None:
        jinja_env.filters.update(filters)

    return jinja_env

parse_date = dateutil.parser.parse
def date_formatter(format_str='%B %d, %Y'):
    return lambda x: format_date(x, format_str)

def rss_date(x):
    """Format a datestr into a format acceptable for RSS"""
    if isinstance(x, str):
        x = dateutil.parser.parse(x)
    return email.utils.format_datetime(x)

def format_date(x, format_str):
    """Format a datestr with a given format string"""
    if isinstance(x, str):
        x = dateutil.parser.parse(x)
    return x.strftime(format_str)


def markdown_filter(extensions=None, extension_configs=None, include_mdx_math=False):
    import markdown
    default_extensions = [
        'markdown.extensions.extra',
        'markdown.extensions.admonition',
        'markdown.extensions.toc',
        'markdown.extensions.codehilite',
        'mdx_math'
    ]
    default_extension_configs = {
            'markdown.extensions.codehilite': {'guess_lang': False}
    }

    if extensions is None:
        extensions = default_extensions
        if not include_mdx_math:
            extensions = extensions[:-1]

    if extension_configs is None:
        extension_configs = default_extension_configs
        if include_mdx_math:
            extension_configs['mdx_math'] = {'enable_dollar_delimiter': True}

    mdfilter = lambda x: markdown.markdown(x, extensions=extensions, extension_configs=extension_configs)
    return mdfilter


_rss_base_src = """
<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
    <title>{{rss_title}}</title>
    <link>{{rss_home_page}}</link>
    <atom:link href="{{rss_link}}" rel="self" type="application/rss+xml" />
    <description>{{rss_description}}</description>
    {% for page in pages %}
    <item>
        {%if page.title is defined and page.title is not none %}<title>{{page.title | striptags | e}}</title>{%endif%}
        <link>{{page.fullhref}}</link>
        <guid isPermaLink="true">{{page.fullhref}}</guid>
        <pubDate>{{page.date | rss_format_date}}</pubDate>
        <description>{{page.content | e}}</description>
    </item>
    {% endfor %}
</channel>
</rss>
""".strip()

def rss_loader(name='builtin/rss_base.xml'):
    import jinja2
    return jinja2.DictLoader({name: _rss_base_src})
