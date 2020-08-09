class ExecutionRule:
    @classmethod
    def wrap(cls, cl):
        if not isinstance(cl, ExecutionRule):
            assert(callable(cl))
            return CallableExecutionRule(cl)
        else:
            return cl

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



