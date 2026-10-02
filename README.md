# HC Works XML Exporter

A small Python script that reads a Slovak Music Centre (HC) works-listing page filtered by one or more database shortcuts, follows its pagination, visits the listed composers, and writes matching works to XML files.

# Vibe-coded using Geminy and Copilot

## Requirements

- Python 3.10 or newer
- Internet access

Install the dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Run

Pass the complete HC works-listing URL as the first command-line argument. The script reads selected shortcuts from the URL's `skratky` query parameters, so use a listing page filtered by the instrument or category you want. Keep the URL quoted because it contains `&` characters.

```powershell
python .\script.py 'https://hc.sk/o-slovenskej-hudbe/diela?meno=&rok_od=&rok_do=&skratky%5B0%5D=tr&skratky_iba=0'
```

XML files are written to the `output` folder beside the script. To choose another folder:

```powershell
python .\script.py 'https://hc.sk/o-slovenskej-hudbe/diela?meno=&rok_od=&rok_do=&skratky%5B0%5D=tr&skratky_iba=0' --output-dir .\my-xml
```

To export a different shortcut, copy the corresponding filtered URL from HC. Multiple selected shortcuts are supported when they appear as `skratky[]` or `skratky[0]`, `skratky[1]`, and so on. Shortcut matching preserves case because HC uses distinct codes such as `a` and `A`.

Each XML file uses a `<Works>` root containing `<Work>` elements with `<Composer>`, `<Title>`, `<SubtitleType>`, `<Instrumentation>`, and `<YearCreated>` fields.

The scraper depends on HC's current page structure and Slovak labels in the source pages. It pauses briefly between requests; a complete export can take a few minutes.
