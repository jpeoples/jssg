import fnmatch

from .execution_rule import FileSys, ExecutionRule

def build(indir, outdir, rules, files="", filesys=None, listeners={}):
    """Build files in `indir` to `outdir` given a set of `rules`"""

    return BuildEnv(indir, outdir, filesys, listeners).build(rules, files)

class BuildEnv:
    def __init__(self, indir, outdir, filesys=None, listeners={}):
        self.indir = indir
        self.outdir = outdir
        self.fs = filesys if filesys is not None else FileSys(indir, outdir)
        self.listeners = listeners

    def _translate_to_execution(self, rule, file):
        if rule is None: return None
        pm, rule = rule
        #inf, outf = execute_path_map(pm, file, self.indir, self.outdir)
        inf = file
        outf = pm(file)
        rule = ExecutionRule.wrap(rule)
        execution, data = rule(self.fs, inf, outf)
        if data is not None:
            for l in self.listeners.values():
                if hasattr(l, "on_data_return"):
                    l.on_data_return(inf, outf, data)
        return execution

    def build(self, rules, files=""):
        executions = []
        if isinstance(files, str):
            files = self.fs.list_all_files(files)
        for file in files:
            rule = _first_matching_rule(rules, file)
            ex = self._translate_to_execution(rule, file)
            if ex is not None:
                executions.append(ex)

        self._run_executions(executions)

    def _run_executions(self, executions):
        exec_state = {}
        for name, l in self.listeners.items():
            if hasattr(l, 'before_execute'):
                exec_state[name] = l.before_execute()

        for ex in executions:
            ex(exec_state)


def _first_matching_rule(rules, path, default=None):
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
