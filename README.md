# METIS CT Data Explorer (Tkinter)

Local desktop GUI for the METIS CT CSV exports. Compatible with Ubuntu and Windows, using **Python 3.10+** and the **Python standard library only** (no pandas, openpyxl, or pip installs).

## Install and run

On Ubuntu:

```bash
sudo apt update
sudo apt install python3-tk
python3 metis_csv_explorer.py
```

On Windows (Python with Tk support):

```powershell
py metis_csv_explorer.py
```

## Workflow

1. Select **Open folder** and choose the METIS `output/` folder, or **Add CSV files** to choose files manually.
2. Select one CSV type and timestamp in the left panel.
3. Browse the 100-row paginated table; search, group columns by category, sort by clicking a column, and double-click a row to see full values.
4. Inspect **Data quality & statistics** (missing %, unique values, numeric min/median/max) and **Data dictionary** (source column names, readable labels, sensitivity flags).
5. **Export current view** generates an Excel workbook including the filtered rows, visible columns, metadata, and dictionary.
6. **Export all datasets** generates separate worksheets for each CSV type and a combined dictionary. Where multiple runs of the same type were loaded, the latest filename (timestamp) is used.

## Supported files

- `CTIQ_*.csv`
- `CTSIZE_*.csv`
- `CTRDSREVENTS_*.csv`
- `CTORGANDOSE_*.csv` 
- `CTSERIESTAGS_*.csv`
- `CT_IQ_Dose_Size_*.csv`

## Design and scientific cautions

- The app runs offline and does not send data to any service.
- It never modifies source CSVs.
- It **does not join raw files automatically**, because one-to-many irradiation-event relationships can duplicate data. For series-level analysis prefer the merged exporter CSV and validate associations.
- A missing-value flag recognizes blanks and common null markers (`N/A`, `null`, etc.).
- Readable labels and inferred column categories do **not** establish units or scientific validity. Verify WED, effective size, NPS, MTF, organ-dose and RDSR field units with the exporter documentation.
- Some source CSVs contain patient IDs, birth dates, accession numbers, UIDs, institution names and other potentially identifiable metadata. The optional **Hide sensitive columns** toggle applies to the current-view export, **not** the Export all datasets function. Treat all exported workbooks as potentially sensitive.
- Values that resemble dates/identifiers are preserved as text rather than converted by Excel. Other numeric columns become numerical cells where possible. Formula-like text is escaped.
- `CTSERIESTAGS` may contain lengthy multi-value entries; a table cell shows a preview, while double-click shows the complete value.
