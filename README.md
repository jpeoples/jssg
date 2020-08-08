# jssg -- Jake's Static Site Generation Library

used to build my personal website.

## Basic Model

The basic idea is to take the set of files in a directory, and match
those files to rules that implement the proper IO behavior.

Rules are compose of two parts: the path map, and the file map.

The path map takes an input file name, and outputs two paths: the input
file, and the output file.

The file map takes two paths and does the actual IO operation to create
the output file from the input file.

jssg's build functions use a two-phase build model, where the first
phase determines what executions to do, and the second actually does
them. By default, this is no different than doing both at the same time.
However, with user hooks, it is possible to collect data during the
first phase that can be used as context during the second phase.

Because the library is intended to make it easy to build static websites
in a highly flexible way, implementing all of these types of objects is
meant to require minimal boilerplate, and as such, the inputs are highly
flexible.

## Implementing a Path Map

jssg is intended to allow you to abstract away the particular
directories you are inputting and outputting to. As such, the file names
that user code sees should typically be relative to these directories.

As such, a PathMap can simply be a function that accepts an input path
(relative to the source directory), and emits a new path (relative to
the build directory).

If you wish to be precise, there is a wrapper, jssg.path_map that can
wrap a callable into a a jssg.PathMap object, but this is not necessary
when using the high-level interface.

## Implementing a File Map

For basic file system operations, jssg provides a file system object
that is aware of the configured source and build directories, such that
you can call file operations on these directly.

If you wish to use other file system operations (or simply don't want to
use the fs object), that is achieved by simply mapping the relative
paths to absolute paths using the `fs.resolve_source(fn)` or
`fs.resolve_build(fn)`

## Execution Rules

Recall that `jssg` has two phases. By default, Path Maps and File Maps
as described above will simply collect all the calls that should be made
to file maps, and execute them after processing all files.

To allow the collection of state, and customization of the delayed
behaviour, you can implement a `jssg.ExecutionRule`. An execution rule
should implement the `__call__(self, fs, inf, outf)` method, and return
two arguments: `execution`, and `state`.

The `execution` return is a function that takes one argument. It's
behaviour can be anything, but this is where FileMaps would typically be
executed.

`state` is an arbitrary piece of data.

When typical FileMaps are used, `execution` ignores its argument and
simply executes the FileMap with the already resolved arguments. The
returned `state` is None.

If an ExecutionMap returns non-None state, then the state object is
passed to the `on_data_return` method of any build listeners.

This allows Execution Rules to be paired with listeners, such that the
returned states can be collected by the listeners.

Build listeners also have `before_execute` methods. These methods return
an arbitrary object that is added to a dictionary with key corresponding
to the listener's name.

After running these callbacks for all listeners, the resulting
dictionary is the state object passed to the executions.

Therefore, combining listeners and ExecutionRules allows the collection
of data that can then be used during execution.

## JinjaFile

The only Execution rule in the library by default is `JinjaFile`. This
object, by default, returns an empty state, and simply writes out the
result of rendering a jinja template during execution.

However, the behaviour can be overridden to keep track of various
data, and to customize the template being used, such that it is possible
to, for example, render a series of pages with a particular template,
while also keeping track of their content, in order to create rss feeds,
blog archives, etc.
