# Third-Party Notices & Open Source Licensing

This repository contains or references documentation, code examples, and technical materials from third-party open-source projects. All ingested and referenced documentation complies with the permissive open-source licensing standards defined in `docs/scope.md`.

---

## 1. Summary of Ingested Documentation by Tier

| Package / Project | Tier | Component / File | License | Canonical Source & Verified Status |
|---|---|---|---|---|
| **Python** | T5 (Lane B) | The Python Tutorial (Python 3.12) | Python Software Foundation License (PSF-2.0) | `https://docs.python.org/3/tutorial/` (HTTP 200) |
| **NumPy** | T6 (Lane B) | NumPy Absolute Basics for Beginners | BSD 3-Clause License | `https://numpy.org/doc/stable/user/absolute_beginners.html` (HTTP 200) |
| **pandas** | T7 (Lane B) | 10 min, Data Structures, Indexing, Missing, GroupBy, Merging | BSD 3-Clause License | `https://pandas.pydata.org/docs/user_guide/` (HTTP 200) |
| **FastAPI** | T1 (Lane A) | Official Tutorial (CORS, BackgroundTasks) | MIT License | `https://fastapi.tiangolo.com/` (HTTP 200) |
| **Pydantic** | T1 (Lane A) | Concepts (Models, Validators) | MIT License | `https://docs.pydantic.dev/` (HTTP 200) |
| **Docker** | T1 (Lane A) | Docker Compose Best Practices & Intro | Apache License 2.0 | `https://docs.docker.com/compose/` (HTTP 200) |
| **psycopg2** | T1 (Lane A) | PostgreSQL Driver Usage Documentation | BSD / PostgreSQL License | `https://www.psycopg.org/docs/` (HTTP 200) |

---

## 2. Explicitly Excluded Non-Permissive Works

- **Pro Git (by Scott Chacon and Ben Straub):**
  - **License:** Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported (`CC BY-NC-SA 3.0`).
  - **Status:** **EXCLUDED & PROHIBITED**.
  - **Reason:** The NonCommercial clause restricts commercial downstream usage, and the ShareAlike clause imposes copyleft licensing obligations. No excerpts, chapters, or derivatives of *Pro Git* are permitted in `corpus/raw/` or vector indexes.

---

## 3. License Texts & Copyright Acknowledgments

### Python Software Foundation License (PSF-2.0)
- **Applies to:** Python 3 Official Documentation (`The Python Tutorial`).
- **Copyright:** (c) 2001-2026 Python Software Foundation. All rights reserved.
- **License Terms:**
  > PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2
  > 
  > 1. This LICENSE AGREEMENT is between the Python Software Foundation ("PSF"), and the Individual or Organization ("Licensee") accessing and otherwise using this software ("Python") in source or binary form and its associated documentation.
  > 2. Subject to the terms and conditions of this License Agreement, PSF hereby grants Licensee a nonexclusive, royalty-free, world-wide license to reproduce, analyze, test, perform and/or display publicly, prepare derivative works, distribute, and otherwise use Python alone or in any derivative version, provided, however, that PSF's License Agreement and PSF's notice of copyright, i.e., "Copyright (c) 2001-2026 Python Software Foundation; All Rights Reserved" are retained in Python alone or in any derivative version prepared by Licensee.

### BSD 3-Clause License (NumPy)
- **Applies to:** NumPy Official Documentation (`NumPy: the absolute basics for beginners`).
- **Copyright:** (c) 2005-2026, NumPy Developers. All rights reserved.
- **License Terms:**
  > Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
  > 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
  > 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
  > 3. Neither the name of the NumPy Developers nor the names of any contributors may be used to endorse or promote products derived from this software without specific prior written permission.

### BSD 3-Clause License (pandas)
- **Applies to:** pandas Official Documentation (User Guide: 10min, Data Structures, Indexing, Missing Data, Groupby, Merging).
- **Copyright:** (c) 2008-2011, AQR Capital Management, LLC, Lambda Foundry, Inc. and PyData Development Team. (c) 2011-2026, Open source contributors. All rights reserved.
- **License Terms:**
  > Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
  > 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
  > 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
  > 3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

### MIT License (FastAPI & Pydantic)
- **Applies to:** FastAPI Documentation ((c) 2018-2026 Sebastián Ramírez) and Pydantic Documentation ((c) 2017-2026 Samuel Colvin and Pydantic contributors).
- **License Terms:**
  > Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
  > The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

### Apache License 2.0 (Docker Documentation)
- **Applies to:** Docker Compose Documentation.
- **Copyright:** (c) Docker, Inc. Licensed under the Apache License, Version 2.0.
- **License Terms:**
  > Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at `http://www.apache.org/licenses/LICENSE-2.0`.
