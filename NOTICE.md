# OpenPipeFlow — Third-Party Notices

OpenPipeFlow is original software (MIT License).
It incorporates or links against the following third-party libraries:

---

## pandapipes
Hydraulic network solver (Newton-Raphson, Darcy-Weisbach, Colebrook-White)

- **Author:** Fraunhofer IEE / University of Kassel
- **Repo:** https://github.com/e2nIEE/pandapipes
- **License:** BSD-3-Clause
- **Used for:** Full pipe network pressure/flow solver

---

## fluids
Fluid dynamics component of the Chemical Engineering Design Library (ChEDL)

- **Author:** Caleb Bell and Contributors (2016–2025)
- **Repo:** https://github.com/CalebBell/fluids
- **License:** MIT
- **Used for:**
  - ISO 5167-2 orifice discharge coefficient (Reader-Harris/Gallagher equation)
    via `fluids.C_Reader_Harris_Gallagher`
  - Darcy friction factor (Clamond method) via `fluids.friction_factor`
  - K ↔ Cd conversion via `fluids.discharge_coefficient_to_K` /
    `fluids.K_to_discharge_coefficient`
- **Citation:** Caleb Bell and Contributors (2016-2025). fluids: Fluid dynamics
  component of Chemical Engineering Design Library (ChEDL).
  https://github.com/CalebBell/fluids

---

## PyQt6
Qt6 bindings for Python

- **Author:** Riverbank Computing Limited
- **License:** GPL v3 / Commercial
- **Used for:** All GUI components

---

## NumPy / SciPy
Numerical computing libraries

- **License:** BSD-3-Clause
- **Used for:** Array operations (via pandapipes dependency)
