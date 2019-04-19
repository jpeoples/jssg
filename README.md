# jssg -- Jake's Static Site Generation Library

jssg is a library for building static websites (in particular it is a
library I use to build my personal website).

It uses jinja2 for templates, providing a markdown filter inside jinja
templates to allow easier writing.

## The Basic Concepts

The `Environment` class is the main class you'll need to work with when
configuring your website. It has a constructor providing a fair amount
of optional arguments and three required arguments (`source_dir`,
`build_dir`, and `base_url`). These are the directory containing all
source files, the directory where the output will be stored, and the url
of the resulting website, respectively.  The class has a single method
`build_dir` which allows you to process all the files in the source
directory or all the files under some subdirectory of the source
directory with a set of build rules.

Build Rules are a combination of a Match Function and a Rule Proc.

A Match Function takes a path relative to the source directory, and
returns True if the file should be processed by this rule, and False
otherwise.

A Rule Proc takes a file name relative to the source directory and
processes it (usually to some other file in the build directory).

The representation for a Build Rule is a tuple `(match_fun, rule_proc)`.
To make the common case easy, if `match_fun` need not be an actual function.
If it is a string, it is treated
as a glob pattern which is matched against the incoming file name. If it
is a sequence, it is taken to be a sequence of glob strings.

Similarly, `rule_proc` can either be a function taking a path relative
to the source dir, and doing some processing, or it can be a tuple
containing two functions: `(path_map, file_map)`

Here `path_map` is a PathMap function. This is a function with signature
```python
def path_map(ctx, file_name):
    # ...
    return in_path, out_path
```
which takes an input `ctx` provided by the `Environment`, and `file_name` which
is the incoming file path, relative to the source directory. The output
is a pair of file paths, namely the input path, and the output path to
which the input file is mapped.

`file_map` is a FileMap function with signature
```python
def file_map(ctx, inpath, outpath):
    # process the files
    return
```
which does the processing mapping inpath to outpath.

In both cases `ctx` is a context object provided by the environment. The
context can be configured by the user via `user_ctx` argument to the
environment constructor and `additional_user_ctx` argument to the
`build_dir` method. Furthermore, after integrating both these contexts,
`build_dir` will also add `indir`, `outdir`, `base_url`, `jenv` (the
jinja env), `render_context` (the jinja render context provided by the
user to env class), `page_collection` (the page collection passed to
`build_dir`, if applicable).
