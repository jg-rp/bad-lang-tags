# Find Bad Lang Tags

Find legacy or broken source code highlighting tags on [Rosetta Code](https://rosettacode.org/wiki/Rosetta_Code) using the [MediaWiki API](https://www.mediawiki.org/wiki/API:Main_page).

The Python script in this repository (`find_bad_lang_tags.py`) is intended to be run as a command line utility, outputting its data as CSV. Progress appears in the form of debugging output, which is always enabled and is written to stderr. `find_bad_lang_tags.py` is currently **read only**. It does not attempt to edit any pages.

Other notable "features":

- Automatically retry GET requests up to 5 times, with back-off.
- Respect `<nowiki>`, `<!-- -->`, `<pre>` and `<code>` tags.
- Respect tags found inside existing `<syntaxhighlight>` and `<lang>` tags.
- Report orphaned `<syntaxhighlight>` and `<lang>` tags.
- Report `<syntaxhighlight>` tags without a `lang` attribute.
- Optionally report unsupported `lang` attributes inside `<syntaxhighlight>` tags.
- Include revision data and _bad tag_ indices in output CSV.
- Target specific namespaces like "talk" or "user" pages.
- Target specific categories like "Draft Programming Tasks"

## Install

`find_bad_lang_tags.py` uses [requests](https://requests.readthedocs.io/en/latest/) and [pygments](https://pygments.org/). To run `find_bad_lang_tags.py`, you can do the following (a copy and paste and other Python package managers would work equally as well.)

Make sure you have [Python >= 3.7 installed](https://www.python.org/downloads/), then clone this repository.

```bash
git clone https://github.com/jg-rp/bad-lang-tags.git
cd bad-lang-tags
```

Install the script dependencies.

```
python -m pip install -U -r requirements.txt
```

Show the command line help message.

```
python find_bad_lang_tags.py --help
```

## Usage

`find_bad_lang_tags.py` outputs CSV data with the following headers. If the `-o` or `--outfile` option is not given, CSV data will be written to the standard output stream.

```plain
page_id
page_title
revision_id
revision_timestamp
lang
tag
start_lineno
end_lineno
unsupported_lang
orphaned
start
end
start_start_index
start_end_index
end_start_index
end_end_index
kind
```

You must specify either a Rosetta Code [namespace](https://www.mediawiki.org/wiki/Manual:Namespace) or [category](https://rosettacode.org/wiki/Special:Categories). When targeting a namespace, an optional page title prefix can be used to filter results further.

### Target a namespace

This example targets task _talk_ pages, stops after it has scanned 50 pages, does not report unsupported `lang` attributes and writes CSV data to `talk.csv` in the current working directory.

```bash
python find_bad_lang_tags.py --namespace=1 --page-limit=50 --skip_unsupported_langs -o talk.csv
```

### Target a category

This example targets all pages in the _Programming Tasks_ category, stops after it has scanned 1500 pages, does not report unsupported `lang` attributes and writes CSV data to `tasks.csv` in the current working directory.

```bash
python find_bad_lang_tags.py --category="Category:Programming Tasks" --page-limit=1500 --skip_unsupported_langs -o tasks.csv
```
