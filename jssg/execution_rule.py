import pathlib
import shutil
import os

class ExecutionRule:
    @classmethod
    def wrap(cls, cl):
        if not isinstance(cl, ExecutionRule):
            assert(callable(cl))
            return CallableExecutionRule(cl)
        else:
            return cl

def two_phase_rule(f):
    class UserExecutionRule(ExecutionRule):
        # preserve help to some degree
        __name__ = f.__name__
        __doc__ = f.__doc__
        def __init__(self, f):
            self.f = f
        def __call__(self, fs, inf, outf):
            return self.f(fs, inf, outf)

    return UserExecutionRule(f)

def _execute_callable_as_filemap(f, fs, inpath, outpath):
    try:
        f(fs.resolve_in(inpath), fs.resolve_out(outpath))
    except TypeError:
        try:
            f(fs, inpath, outpath)
        # If it is a string func we get a TypeError due to too many args
        except TypeError as e:
            assert(callable(op))
            s = fs.read(inf)
            outs = f(s)
            fs.write(outf, outs)

# TODO: Should we really return something in state here?
class CallableExecutionRule(ExecutionRule):
    def __init__(self, cl):
        self.callable = cl

    def __call__(self, fs, inf, outf):
        ex = lambda state: _execute_callable_as_filemap(self.callable, fs, inf, outf)
        return ex, dict(type='filemap', function=self.callable, data=(inf, outf))

def copy_file(fs, inpath, outpath):
    fs.copy(inpath, outpath)

def list_all_files(d, rel_to=None):
    if rel_to is None:
        rel_to = d

    for directory_path, _, file_names in os.walk(d):
        for fn in file_names:
            yield pathlib.Path(directory_path, fn).relative_to(rel_to).as_posix()

class FileSys:
    def __init__(self, indir, outdir):
        self.indir = indir
        self.outdir = outdir

    def resolve_in(self, inf):
        return pathlib.Path(self.indir, inf).as_posix()

    def resolve_out(self, outf):
        return pathlib.Path(self.outdir, outf).as_posix()


    def copy(self, inf, outf):
        self.ensure_dir(outf)
        shutil.copy(self.resolve_in(inf), self.resolve_out(outf))

    def read(self, inf):
        return open(self.resolve_in(inf), 'r', encoding='utf-8').read()

    def write(self, outf, s):
        self.ensure_dir(outf)
        open(self.resolve_out(outf), 'w', encoding='utf-8').write(s)

    def ensure_dir(self, outf):
        outf = self.resolve_out(outf)
        loc = pathlib.Path(outf).parent
        if not loc.is_dir():
            loc.mkdir(parents=True)

    def list_all_files(self, d=""):
        return list_all_files(self.resolve_in(d), rel_to=self.indir)

