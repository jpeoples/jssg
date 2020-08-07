import os
import shutil
import fnmatch
import pathlib
import types

from . import jinja_utils
from .execution_rule import ExecutionRule
from .jinja_utils import JinjaRenderable

class Environment:
    """The high level interface for jssg"""
    def __init__(self, build_env, jinja_file=None, **kwargs):
        self.build_env = build_env
        self.jinja_file = jinja_file

        if self.jinja_file is None:
            self.jinja_filters = {
                'format_date': jinja_utils.date_formatter(),
                'rss_format_date': jinja_utils.rss_date,
                # 'parse_date': jinja_utils.parse_date,
            }
            try:
                import markdown
                self.jinja_filters["markdown"] = jinja_utils.markdown_filter(include_mdx_math=True)
            except ImportError:
                pass
            self.jinja_search_paths = (".", )
            self.jinja_search_prefix_paths = ()
            self.jinja_additional_loaders = [jinja_utils.rss_loader()]
            #self.jinja_base_context = jinja_utils.Context()
            self.jinja_base_context = kwargs.pop('jinja_base_context', jinja_utils.Context())
            #self.jinja_base_context = {}
            #self.jinja_immediate_context = []
            
    @classmethod
    def default(cls, indir, outdir, **kwargs):
        return cls(BuildEnv(indir, outdir), **kwargs)

    @property
    def jinja(self):
        if self.jinja_file is None:
            jenv = jinja_utils.jinja_env(self.jinja_search_paths, self.jinja_search_paths, self.jinja_additional_loaders, filters=self.jinja_filters)
            self.jinja_file = jinja_utils.JinjaFile(jenv, self.jinja_base_context)
        return self.jinja_file

    @property
    def ignore_file(self):
        return None

    @property
    def mirror_file(self):
        return (mirror_path, copy_file)

    def execute(self, rp, fn):
        self.build_env.execute(rp, fn)

    def build(self, rules, files=""):
        self.build_env.build(rules, files)

    


def mirror_path(fn):
    return fn

def replace_extensions(suff):
    def op(fn):
        path = pathlib.Path(fn)
        # remove suffixes
        while path.suffix:
            path = path.with_suffix('')
        return path.with_suffix(suff).as_posix()
    return op

remove_extensions = replace_extensions("")

def remove_internal_extensions(fn):
    pathobj = pathlib.Path(fn)
    op = replace_extensions(pathobj.suffix)
    return op(fn)

def relative_path(fn, directory):
    return pathlib.Path(fn).relative_to(directory).as_posix()

def execute_path_map(op, fn, indir, outdir):
    try:
        inpath, outpath = op(fn, indir, outdir)
        return inpath, outpath
    except TypeError:
        outfn = op(fn)
        return (pathlib.Path(indir, fn).as_posix(),
                pathlib.Path(outdir, outfn).as_posix())


class FileSys:
    def copy(self, inf, outf):
        self.ensure_dir(outf)
        shutil.copy(inf, outf)

    def read(self, inf):
        return open(inf, 'r', encoding='utf-8').read()

    def write(self, outf, s):
        self.ensure_dir(outf)
        open(outf, 'w', encoding='utf-8').write(s)

    def ensure_dir(self, outf):
        loc = pathlib.Path(outf).parent
        if not loc.is_dir():
            loc.mkdir(parents=True)


def list_all_files(d, rel_to=None):
    if rel_to is None:
        rel_to = d

    for directory_path, _, file_names in os.walk(d):
        for fn in file_names:
            yield pathlib.Path(directory_path).joinpath(fn).relative_to(rel_to).as_posix()



class FileMapper:
    def __init__(self, filesys=None):
        self.filesys = filesys if filesys is not None else FileSys()

    def execute(self, op, inpath, outpath):
        try:
            op(inpath, outpath)
        except TypeError:
            try:
                op(self.filesys, inpath, outpath)
            # If it is a string func we get a TypeError due to too many args
            except TypeError as e:
                assert(callable(op))
                self.wrapped_execute(op, inpath, outpath)

    def wrapped_execute(self, op, inpath, outpath):
        s = self.filesys.read(inpath)
        outs = op(s)
        self.filesys.write(outpath, outs)


def copy_file(fs, inpath, outpath):
    fs.copy(inpath, outpath)




class BuildEnv:
    def __init__(self, indir, outdir, filemapper=None):
        self.indir = indir
        self.outdir = outdir
        self.filemapper = filemapper if filemapper is not None else FileMapper()
        self.reset_state()
        self.listeners = {}

    def add_listener(self, name, listener):
        self.listeners[name] = listener


    def translate_to_execution(self, rule, file):
        if rule is None: return
        pm, rule = rule
        inf, outf = execute_path_map(pm, file, self.indir, self.outdir)
        rule = ExecutionRule.wrap(rule)
        execution, data = rule(self.filemapper.filesys, inf, outf)
        if data is not None:
            for l in self.listeners.values():
                if hasattr(l, "on_data_return"):
                    l.on_data_return(inf, outf, data)
        self.add_execution(execution)
        return


    def add_execution(self, execution):
        self.execution_sequence.append(execution)

    def build(self, rules, files=""):
        if isinstance(files, str):
            files = list_all_files(os.path.join(self.indir, files), rel_to=self.indir)
        for file in files:
            rule = first_matching_rule(rules, file)
            self.translate_to_execution(rule, file)

        self.flush_execution()

    def flush_execution(self):
        exec_state = {}
        for name, l in self.listeners.items():
            if hasattr(l, 'before_execute'):
                exec_state[name] = l.before_execute()

        for ex in self.execution_sequence:
            ex(exec_state)

        self.reset_state()

    def reset_state(self):
        self.execution_sequence = []

def first_matching_rule(rules, path, default=None):
    for (rule, result) in rules:
        if _match_single_rule(rule, path):
            return result
    return default

def _match_single_rule(rule, path):
    if isinstance(rule, str):
        result = fnmatch.fnmatch(path, rule)
        return result
    for r in rule:
        if _match_single_rule(r, path):
            return True
    return False
