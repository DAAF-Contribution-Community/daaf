# Interactive UI Elements

## Core Concept

marimo provides reactive UI elements via `mo.ui`. When a user interacts with an element:
1. The new value is sent to Python
2. All cells referencing that element automatically re-run

**No callbacks required** - just read `.value` in another cell.

## Basic Pattern

```python
# Cell 1: Create and display
slider = mo.ui.slider(1, 100, value=50, label="Amount")
slider

# Cell 2: Use the value (auto-runs on interaction)
f"You selected: {slider.value}"
```

**Important**: Elements must be assigned to a **global variable** for interactions to trigger re-runs.

## Common Elements

### Slider

```python
slider = mo.ui.slider(
    start=0,
    stop=100,
    value=50,          # Default
    step=1,            # Increment
    label="Value",
    show_value=True
)
```

### Range Slider

```python
range_slider = mo.ui.range_slider(
    start=0,
    stop=100,
    value=[20, 80],    # [low, high]
    label="Range"
)
# range_slider.value returns tuple (low, high)
```

### Number Input

```python
number = mo.ui.number(
    start=0,
    stop=100,
    value=50,
    step=0.1,
    label="Enter number"
)
```

### Dropdown

```python
dropdown = mo.ui.dropdown(
    options=["Option A", "Option B", "Option C"],
    value="Option A",
    label="Select one"
)

# With dict for value mapping
dropdown = mo.ui.dropdown(
    options={"Display A": "value_a", "Display B": "value_b"},
    label="Select"
)
```

### Multiselect

```python
multi = mo.ui.multiselect(
    options=["Red", "Green", "Blue"],
    value=["Red"],     # Default selection
    label="Colors"
)
# multi.value is a list
```

### Radio Buttons

```python
radio = mo.ui.radio(
    options=["Small", "Medium", "Large"],
    value="Medium",
    label="Size"
)
```

### Checkbox

```python
checkbox = mo.ui.checkbox(value=False, label="Enable feature")
# checkbox.value is True/False
```

### Switch

```python
switch = mo.ui.switch(value=False, label="Dark mode")
```

### Text Input

```python
text = mo.ui.text(
    value="",
    placeholder="Enter name...",
    label="Name",
    max_length=100
)
```

### Text Area

```python
textarea = mo.ui.text_area(
    value="",
    placeholder="Enter description...",
    label="Description",
    rows=5
)
```

### Date Picker

```python
date = mo.ui.date(
    value=datetime.date.today(),
    label="Select date"
)

# Date range
date_range = mo.ui.date_range(
    value=(start_date, end_date),
    label="Date range"
)
```

### File Upload

```python
file = mo.ui.file(
    filetypes=[".csv", ".json"],
    multiple=False,
    label="Upload file"
)
# file.value is a FileUploadResults object
# file.value[0].contents for bytes
# file.value[0].name for filename
```

### Button

```python
button = mo.ui.button(label="Click me")
# button.value increments on each click

# With callback
button = mo.ui.button(
    label="Submit",
    on_click=lambda value: print("Clicked!")
)
```

### Run Button

Triggers cell execution only when clicked:

```python
run = mo.ui.run_button(label="Run analysis")

mo.stop(not run.value)  # Stop if not clicked
# Expensive computation below only runs on click
result = expensive_analysis()
```

## Tables

### Interactive Table

```python
table = mo.ui.table(
    data=df,                    # DataFrame or list of dicts
    selection="multi",          # "single", "multi", "single-cell", "multi-cell", or None
    pagination=True,
    page_size=10
)
# table.value is the selected rows, in the same format as the input data
```

### Display-Only Table Options

Defaults in 0.25.0 (`marimo/_plugins/ui/_impl/table.py`), with the switch for a plain preview:

| Option | Default | For a plain preview |
|--------|---------|---------------------|
| `selection` | `"multi"` (row checkboxes) | `selection=None` |
| `pagination` | on above 10 rows | leave on, or set `page_size` |
| `page_size` | 10 | e.g. `page_size=25` |
| `show_column_summaries` | on for up to 40 columns and more than 10 rows (per-column stats and charts) | `show_column_summaries=False` (`"stats"` or `"chart"` keep one part) |
| `show_download` | on for DataFrames | `show_download=False` |
| `show_search` | on (keyword-only) | `show_search=False` |
| `show_data_types` | on | `show_data_types=False` |
| `max_height` | none | pixels; scrolls with a sticky header |
| `hidden_columns` / `visible_columns` | none | mutually exclusive column subsets |
| `column_widths` | none | `{column: pixels}` |

```python
# A preview with no selection checkboxes, column summaries, or download button
mo.ui.table(df.head(100), selection=None, show_column_summaries=False, show_download=False)

# Reuse one set of display options (mo.ui.table.Display is a TypedDict)
cfg = mo.ui.table.Display(show_search=False, show_download=False)
mo.ui.table(df.head(100), **cfg)
```

Column summaries compute statistics and charts over the rows passed in. In a DAAF Stage 9 notebook the canonical preview is the form `.claude/agents/notebook-assembler.md` emits; change it there, not cell by cell.

`mo.ui.table.lazy(lazy_frame, page_size=None, preload=False)` shows a Polars LazyFrame (or Ibis table, DuckDB relation) without loading it, then loads the first rows on request; lazy tables have no pagination or selection.

### Data Editor

```python
editor = mo.ui.data_editor(df)
# editor.value is the modified DataFrame
```

### DataFrame Transformer

No-code data transformations:

```python
transformer = mo.ui.dataframe(df)
# transformer.value is transformed DataFrame
```

## Composite Elements

### Form (Gate Updates on Submit)

Wrap any element to require explicit submission:

```python
form = mo.ui.text(label="Query").form(submit_button_label="Search")
# form.value only updates when submitted
```

Or wrap multiple elements using `.batch().form()`:

```python
form = mo.md("""
**Search Parameters**

Query: {query}
Max results: {max_results}
""").batch(
    query=mo.ui.text(placeholder="Enter search term"),
    max_results=mo.ui.number(start=1, stop=100, value=10),
).form()
# form.value is {"query": "...", "max_results": 10}
```

### Array (Dynamic List of Elements)

```python
# When number of elements is determined at runtime
sliders = mo.ui.array([
    mo.ui.slider(0, 100, label=f"Slider {i}")
    for i in range(n)
])
# sliders.value is list of values
# Access individual: sliders[0]
```

### Dictionary (Named Elements)

```python
inputs = mo.ui.dictionary({
    "name": mo.ui.text(label="Name"),
    "age": mo.ui.number(0, 120, label="Age"),
    "active": mo.ui.checkbox(label="Active")
})
# inputs.value is {"name": "...", "age": 25, "active": True}
# Access: inputs["name"]
```

### Batch (Custom Layout)

Group elements with custom HTML/markdown layout:

```python
batch = mo.ui.batch(
    mo.md("""
    # Configuration
    
    Temperature: {temp}
    
    Model: {model}
    """),
    {"temp": mo.ui.slider(0, 1), "model": mo.ui.dropdown(["gpt-4", "claude"])}
)
# batch.value is {"temp": 0.7, "model": "gpt-4"}
```

## Tabs (for UI Organization)

```python
tabs = mo.ui.tabs({
    "Data": mo.md("Data content here"),
    "Settings": settings_form,
    "Results": results_table
})
```

## Code Editor

```python
code = mo.ui.code_editor(
    value="print('hello')",
    language="python"
)
# code.value is the code string
```

## Chat Interface

```python
def respond(messages, config):
    # messages is list of {"role": "user"|"assistant", "content": "..."}
    return "AI response here"

chat = mo.ui.chat(respond)
```

## Tips

### Embed in Markdown

```python
slider = mo.ui.slider(1, 10)
mo.md(f"Choose value: {slider}")
```

### Conditional Display

```python
show_advanced = mo.ui.checkbox(label="Show advanced")

mo.md(f"""
Basic options here...

{mo.md("**Advanced Options**") if show_advanced.value else ""}
""")
```

### Late Binding in Loops

```python
# WRONG: All callbacks reference last i
buttons = mo.ui.array([
    mo.ui.button(on_click=lambda v: print(i))  # Bug!
    for i in range(10)
])

# CORRECT: Bind i explicitly
buttons = mo.ui.array([
    mo.ui.button(on_click=lambda v, i=i: print(i))
    for i in range(10)
])
```

## Summary Table

| Element | Returns | Use Case |
|---------|---------|----------|
| `slider` | number | Numeric selection |
| `dropdown` | string/value | Single choice |
| `multiselect` | list | Multiple choices |
| `checkbox` | bool | Toggle |
| `text` | string | Short input |
| `text_area` | string | Long input |
| `table` | list[row] | Data selection |
| `file` | FileUpload | File input |
| `form` | dict | Gated submission |
| `array` | list | Dynamic elements |
| `dictionary` | dict | Named elements |
