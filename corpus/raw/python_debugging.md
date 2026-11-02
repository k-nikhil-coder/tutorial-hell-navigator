# Python Errors, Virtual Environments and Debugging

## ModuleNotFoundError Despite pip list Showing the Package

The most common cause is that the Python interpreter executing the script is not the same interpreter whose site-packages received the package.

Diagnosis steps:

```bash
which python
which pip
python -c "import sys; print(sys.executable); print(sys.path)"
python -m pip list
```

Always install with the same interpreter you will use to run the code:

```bash
python -m pip install package_name
# or inside a venv
source .venv/bin/activate
python -m pip install package_name
```

A shell alias that forces a system Python, or an IDE that points to a different interpreter, frequently produces this mismatch.

## Logging Format KeyError

A traceback that ends with:

```
KeyError: 'mesage'
```

almost always means the format string passed to `logging.basicConfig` or a `Formatter` contains a misspelled placeholder.

Search the project for the exact string that appears in the KeyError:

```python
# wrong
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(mesage)s')

# correct
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s')
```

## Virtual Environment Activation and Externally Managed Environments

On modern Linux distributions (Debian, Ubuntu, Fedora) the system Python is marked as "externally managed". Running plain `pip install` outside a virtual environment fails with:

```
error: externally-managed-environment
```

Create and use a venv:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Never use `--break-system-packages` for application work.

## Reading Tracebacks

A typical traceback has the most recent call last. Start reading from the bottom:

1. The final exception type and message tell you what failed.
2. The file and line number immediately above show where the exception was raised.
3. Frames higher up show the call chain that led to the failure.

For deeper inspection use `pdb`:

```python
import pdb; pdb.set_trace()
# or
breakpoint()   # Python 3.7+
```

Conditional breakpoints can be set with:

```python
if some_condition:
    breakpoint()
```
