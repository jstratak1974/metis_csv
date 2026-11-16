# METIS CT Data Explorer — De-identification edition

A separate, full Tkinter desktop app based on `metis\_csv\_explorer.py` from [metis\_csv](https://github.com/jstratak1974/metis_csv). It preserves the original viewer, pagination, searching, grouping, data quality, data dictionary, and **original/unmodified** CSV viewing and Excel export controls, and adds **De-ID Excel** and **De-ID CSVs**.

## Run

Ubuntu: `sudo apt install python3-tk` then `python3 metis\_csv\_explorer\_deid.py`.

Windows: `py metis\_csv\_explorer\_deid.py`.

No third-party Python packages are necessary for the application. The optional `build\_windows.bat` uses PyInstaller to make a Windows executable; run it **on Windows**.

## Safe workflow

1. Import the METIS `output/` directory using **Open folder**, or **Add CSV files**.
2. Explore raw datasets locally; **Export current view** and **Export all datasets** are the original exports and may retain identifying information.
3. Choose **De-ID Excel** for a multi-sheet workbook, or **De-ID CSVs** for individual CSVs and an `EXPORT\_AUDIT.json` field inventory.
4. The app uses the latest filename for each CSV type when multiple timestamps have been loaded, just like the original **Export all datasets** button.
5. Pseudonyms are consistent among the six selected CSVs **within one batch**. Export again and the pseudonyms are deliberately different. Do **not** compare pseudonyms across independently generated batches.
6. Inspect the resulting datasets and obtain institutional authorization before external sharing.

## De-identification rules

* `Patient\_ID`: replaced with a new `PATIENT\_...` pseudonym.
* Study/Series/SOP/Frame-of-Reference/Irradiation-Event UIDs: replaced with new valid DICOM `2.25.<integer>` UIDs, consistently across file types.
* Accession numbers: replaced with `ACCESSION\_...` pseudonyms.
* Full birth dates, names, clinicians/operators, exact dates/times, scanner serial numbers, source paths, free-text study/series descriptions and error messages: excluded.
* Existing patient ages in years are kept; 90+ are grouped as `90+`. Date of birth is **not** used to calculate age.
* A conservative allowlist retains important quantitative dose, image-quality, WED/size and acquisition fields; unknown fields are excluded automatically.
* No mapping table, original identifiers or pseudonymization secret is exported. A random secret is used in memory for every export operation.
* Original CSVs are never changed.

**Data quality:** Only numerical values (or simple numeric vectors) are kept in quantitative columns; invalid free text is blanked, not copied. Values should be inspected, and source units verified, before use.

## IMPORTANT: NOT AUTOMATIC GDPR ANONYMIZATION

The exported data are **pseudonymized / de-identified research data**, not necessarily anonymous under GDPR. Age, sex, weight, size, uncommon doses, scanner metadata, and repeated observations may be quasi-identifiers, and a mapping may exist in the source PACS/RIS. This software does not certify irreversibility of re-identification, does not assess small-cell risk, and does not replace an institutional DPIA/privacy review, clinical approval, or data transfer agreement. It intentionally omits some free-text scientific metadata such as protocol descriptions because these could carry personal identifiers.

