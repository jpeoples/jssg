class ExecutionRule:
    """Parent class for Execution Rules.

    Execution Rules are callables with signature
        (fs, inf, outf) -> ex, state
    where `ex` is a callable accepting a single argument (the exec_state),
    and state is any data return value that can be passed to listeners during
    building.

    This class exists simply to serve as a notification that a given object is
    to be interpreted as an ExecutionRule, rather than a FileMap.
    """
    @classmethod
    def wrap(cls, cl):
        """Ensure the input is an execution rule. If it is not already an
        instance of ExecutionRule, the input is assumed to be a file map
        and is thus wrapped by FileMapExecutionRule
        """
        if not isinstance(cl, ExecutionRule):
            assert(callable(cl))
            return FileMapExecutionRule(cl)
        else:
            return cl

def execution_rule(f):
    """Decorate a function implementing the Execution Rule interface (as opposed to the FileMap interface).

    This is a convenience tool to implement ExecutionRules with simple functions.
    Without the decorator, such a function will be erroneously interpreted as a
    file map.
    """
    return _ExecutionRuleFunction(f)

class _ExecutionRuleFunction(ExecutionRule):
    def __init__(self, f):
        self.f = f
    def __call__(self, fs, inf, outf):
        return self.f(fs, inf, outf)

# TODO : Implement this decision based on number of input arguments, so
# as to avoid possible problems due to TypeError exceptions raised for
# other reasons.
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
class FileMapExecutionRule(ExecutionRule):
    """Wrap a file map callable into an ExecutionRule interface (ignoring the exec_state)

    There are three valid file map interfaces. They are used with the following priority:
        f(inpath, outpath)
            call with the actual path to the input file and output file. The function
            should then execute the logic to produce outpath from inpath.
        f(fs, inf, outf):
            call with the names of inf and outf (relative to source and build dir, resp),
            along with the file system object. The fs object can then be used to resolve
            the actual paths, or perform basic, common file system operations.
        f(str) -> str
            Take a string representing the contents of the input file, and return a string
            that contains the contents of the output file.
    """
    def __init__(self, cl):
        self.callable = cl

    def __call__(self, fs, inf, outf):
        ex = lambda state: _execute_callable_as_filemap(self.callable, fs, inf, outf)
        return ex, dict(type='filemap', function=self.callable, data=(inf, outf))

def copy_file(fs, inpath, outpath):
    """File map copying the input to the output."""
    fs.copy(inpath, outpath)
