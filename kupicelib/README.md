# README <!-- omit in toc -->
_current version: 1.0.0_

*kupicelib* is a modified version of [spicelib](https://github.com/nunobrum/spicelib), a toolchain of python utilities designed to interact with spice simulators, including:

* LTspice
* Ngspice
* QSPICE
* Xyce

**Table of Contents**

- [What is kupicelib](#what-is-kupicelib)
- [Original Project](#original-project)
- [How to Install](#how-to-install)
- [How to use](#how-to-use)
- [LICENSE](#license)

## What is kupicelib

kupicelib is a fork of the spicelib project with the following modifications:
- [List your modifications/enhancements here]
- [For example: Added support for XYZ simulator]
- [For example: Enhanced performance for large circuit simulations]

## Original Project

This package is based on [spicelib](https://github.com/nunobrum/spicelib) originally created by Nuno Brum. All credit for the core functionality goes to the original author and contributors. This modified version is distributed in accordance with the original GPL-3.0 license.

## How to Install

```
pip install kupicelib
```

## How to use

kupicelib maintains the same API as spicelib, with a few enhancements. Simply import from kupicelib instead of spicelib:

```python
from kupicelib import RawRead
from kupicelib.editor.spice_editor import SpiceEditor
from kupicelib.simulators.ltspice_simulator import LTspice
# etc.
```

[Include usage examples as needed]

## LICENSE

This project is licensed under the GPL-3.0 License - see the LICENSE file for details. 