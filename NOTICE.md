# OpenPipeFlow — Third-Party Notices

OpenPipeFlow is original software released under the MIT License.
It incorporates or links against the following third-party libraries at runtime,
and uses PyInstaller to produce a standalone Windows executable.

---

## PyQt6  `6.10.2`
Qt6 Python bindings

- **Author:** Riverbank Computing Limited
- **Website:** https://www.riverbankcomputing.com/software/pyqt/
- **License:** GPL v3 / Commercial (Riverbank Commercial License)
- **Used for:** All GUI components — main window, canvas, dockable panels,
  toolbars, menus, dialogs, spinboxes, and the QGraphicsScene pipe canvas

---

## pandapipes  `0.13.0`
Pipe network simulation framework

- **Author:** Fraunhofer Institute for Energy Economics and Energy System
  Technology (IEE), University of Kassel, and Contributors
- **Website:** https://www.pandapipes.org
- **Repo:** https://github.com/e2nIEE/pandapipes
- **License:** BSD-3-Clause
- **Used for:** Full pipe-network pressure/flow solver —
  Newton-Raphson iteration, Darcy-Weisbach friction (Colebrook-White),
  junction pressures, and pipe-flow results
- **Citation:** Lèo Thurner, Alexander Scheidler, Florian Schäfer,
  Jan-Hendrik Menke, Julian Dollichon, Friederike Meier, Steffen Moll,
  Martin Braun — pandapipes: An Open-Source Piping Grid Calculation Package
  for Multi-Energy Grid Simulations. Energies 2020, 13(9), 2408.
  https://doi.org/10.3390/en13092408

---

## pandapower  `3.3.0`
Power system analysis framework (pandapipes dependency)

- **Author:** University of Kassel and Contributors
- **Website:** https://www.pandapower.org
- **Repo:** https://github.com/e2nIEE/pandapower
- **License:** BSD-3-Clause
- **Used for:** Required by pandapipes for network topology and solver
  infrastructure; not called directly by OpenPipeFlow

---

## fluids  `1.3.0`
Fluid dynamics component of the Chemical Engineering Design Library (ChEDL)

- **Author:** Caleb Bell and Contributors (2016–2025)
- **Repo:** https://github.com/CalebBell/fluids
- **License:** MIT
- **Used for:**
  - ISO 5167-2 orifice discharge coefficient (Reader-Harris/Gallagher 1998)
    via `fluids.C_Reader_Harris_Gallagher`
  - Darcy friction factor (Clamond iterative method)
    via `fluids.friction_factor`
  - K ↔ Cd conversion (ASME MFC-3M formula)
    via `fluids.discharge_coefficient_to_K` / `fluids.K_to_discharge_coefficient`
  - Fluid property data via `fluids.IAPWS97`
- **Citation:** Caleb Bell and Contributors (2016-2025). fluids: Fluid dynamics
  component of Chemical Engineering Design Library (ChEDL).
  https://github.com/CalebBell/fluids

---

## NumPy  `2.4.2`
Fundamental package for scientific computing with Python

- **Author:** Travis E. Oliphant et al. / NumPy Developers
- **Website:** https://numpy.org
- **License:** BSD-3-Clause
- **Used for:** Numerical array operations (via pandapipes/pandapower dependency)

---

## SciPy  `1.17.1`
Scientific and technical computing library

- **Author:** SciPy Developers
- **Website:** https://scipy.org
- **License:** BSD-3-Clause
- **Used for:** Sparse linear algebra, optimisation routines
  (via pandapipes/pandapower dependency)

---

## pandas  `2.3.3`
Data analysis and manipulation library

- **Author:** Wes McKinney and the pandas Development Team
- **Website:** https://pandas.pydata.org
- **License:** BSD-3-Clause
- **Used for:** Tabular result DataFrames produced by pandapipes
  (pandapower/pandapipes dependency); results are read back from
  `net.res_pipe`, `net.res_pump`, and `net.res_junction`

---

## NetworkX  `3.6.1`
Network analysis library

- **Author:** NetworkX Developers (Aric Hagberg, Dan Schult, Pieter Swart)
- **Website:** https://networkx.org
- **License:** BSD-3-Clause
- **Used for:** Graph topology and connectivity analysis
  (pandapipes dependency)

---

## PyInstaller  *(build tool only — not distributed at runtime)*
Packages Python applications into standalone executables

- **Author:** The PyInstaller Development Team
- **Website:** https://pyinstaller.org
- **Repo:** https://github.com/pyinstaller/pyinstaller
- **License:** GPL v2 (bootloader exception — see note below)
- **Used for:** Building the standalone `OpenPipeFlow.exe` for Windows
- **Note:** PyInstaller's *bootloader* is compiled into the produced EXE.
  The PyInstaller project grants a specific exception that allows the
  bootloader to be used in proprietary/non-GPL applications:
  *"The bootloader which is embedded in each PyInstaller-generated executable
  is not subject to the GPL. You may use it without any restrictions."*
  See https://pyinstaller.org/en/stable/license.html

---

## License texts

Full license texts for BSD-3-Clause, MIT, and GPL v3 libraries are available
from their respective repositories linked above.

The BSD-3-Clause license (for pandapipes, pandapower, NumPy, SciPy, pandas,
NetworkX) requires the following in redistributions:
> Redistributions in binary form must reproduce the above copyright notice,
> this list of conditions and the following disclaimer in the documentation
> and/or other materials provided with the distribution.

This notice file serves as that documentation requirement for the bundled
OpenPipeFlow EXE distribution.
