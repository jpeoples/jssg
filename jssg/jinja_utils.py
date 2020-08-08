from .execution_rule import ExecutionRule


class _RendererImpl:
    def __init__(self, name=None, load_file=None, create_state=None, obj=None):
        self._name = name
        self._load_file = load_file
        self._create_state = create_state
        self._obj = obj

    def _get_load(self):
        if self._load_file: return self._load_file
        if self._obj and hasattr(self._obj, 'load_file'):
            return self._obj.load_file

        def _default_load(jf, fs, inf, outf, ctx):
            s = fs.read(inf)
            t = jf.env.from_string(s)
            return t
        return _default_load

    def _get_create_state(self):
        if self._create_state: return self._create_state
        if self._obj and hasattr(self._obj, 'create_state'):
            return self._obj.create_state

        def _default_create_state(jf, fs, inf, outf, ctx):
            if self._name is None: return None
            return dict(type=self._name, context=ctx)

        return _default_create_state


    def load_file(self, jf, fs, inf, outf, ctx):
        return self._get_load()(jf, fs, inf, outf, ctx)

    def create_state(self, jf, fs, inf, outf, ctx):
        return self._get_create_state()(jf, fs, inf, outf, ctx)

class _JinjaRenderer(ExecutionRule):
    def __init__(self, jf, impl):
        self.jf = jf
        self.impl = impl

    def __call__(self, fs, inf, outf):
        ctx = self.jf.immediate_context(fs, inf, outf)
        template = self.impl.load_file(self.jf, fs, inf, outf, ctx)
        state = self.impl.create_state(self.jf, fs, inf, outf, ctx)
        execution = lambda state: fs.write(outf,
                template.render(ctx, user_context=state))
        return execution, state

class JinjaFile(ExecutionRule):
    def __init__(self, env, ctx, hooks=None):
        self.env = env
        self.ctx = ctx
        self.hooks = hooks if hooks is not None else []

    def render_markdown_string(self, s, ctx):
        # TODO: Something better than looking up in dict?
        md = self.env.filters['markdown']
        return md(self.env.from_string(s).render(ctx))


    def immediate_context(self, fs, inf, outf):
        ctx = self.ctx.copy()
        if len(self.hooks) > 0:
            for hook in self.hooks:
                ctx.update(hook(self.ctx, inf, outf))
        return ctx

    def renderer(self, *, name=None, obj=None, load_file=None, create_state=None):
        if load_file is not None or create_state is not None:
            assert obj is None

        obj = _RendererImpl(name, load_file, create_state, obj)
        return _JinjaRenderer(self, obj)

    def __call__(self, fs, inf, outf):
        return self.renderer()(fs, inf, outf)

# Code for configuring libs, like the jinja_environment
def jinja_env(search_paths=(), prefix_paths=(), additional_loaders=None, filters=None, support_rss=True, rss_name="builtin/rss_base.xml"):
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

    if filters is None:
        filters = {}

    if additional_loaders is None:
        additional_loaders = []


    user_prefix_loader = jinja2.PrefixLoader(
            {prefix: jinja2.FileSystemLoader(path)
                for path, prefix in normalize_prefix_paths(prefix_paths)})

    user_loader = jinja2.ChoiceLoader([jinja2.FileSystemLoader(path) for path in search_paths])



    if support_rss:
        additional_loaders.append(rss_loader(rss_name))
        filters['rss_format_date'] = rss_date


    if additional_loaders:
        additional_loader = jinja2.ChoiceLoader(additional_loaders)

    loader = jinja2.ChoiceLoader([user_loader, user_prefix_loader]+additional_loaders)

    jinja_env = jinja2.Environment(loader=loader, undefined=jinja2.StrictUndefined)

    if filters:
        jinja_env.filters.update(filters)

    return jinja_env

def markdown_filter(extensions=None, extension_configs=None):
    import markdown
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

def rss_date(x):
    """Format a datestr into a format acceptable for RSS"""
    import dateutil.parser
    import email.utils

    if isinstance(x, str):
        x = dateutil.parser.parse(x)
    return email.utils.format_datetime(x)

def rss_loader(name='builtin/rss_base.xml'):
    import jinja2
    return jinja2.DictLoader({name: _rss_base_src})

def date_formatter(format_str='%B %d, %Y'):
    return lambda x: format_date(x, format_str)


def format_date(x, format_str):
    """Format a datestr with a given format string"""
    import dateutil.parser
    if isinstance(x, str):
        x = dateutil.parser.parse(x)
    return x.strftime(format_str)
