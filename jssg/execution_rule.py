class ExecutionRule:
    @classmethod
    def wrap(cls, cl):
        if not isinstance(cl, ExecutionRule):
            assert(callable(cl))
            return CallableExecutionRule(cl)
        else:
            return cl

class CallableExecutionRule(ExecutionRule):
    def __init__(self, cl):
        self.callable = cl

    def __call__(self, fs, inf, outf):
        ex = lambda state: self.callable(fs, inf, outf)
        return ex, dict(type='wrapped', data=(inf, outf))

