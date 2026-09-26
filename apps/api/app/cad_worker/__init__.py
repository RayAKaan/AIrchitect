"""The isolated CAD/BIM worker.

Everything in this package runs under a *separate* virtualenv that contains the
CAD libraries (``cadquery-ocp`` / OCCT 7.9.3 and ``ifcopenshell`` 0.8.5). The API
application never imports this package, and this package never imports the API
application. They communicate only by JSON over a pipe.

That is what keeps the LGPL boundary asserted in
``docs/legal/PHASE-5-OPEN-SOURCE-LICENSE-AUDIT.md`` a property of the system
rather than a hope, and it is why the API image can stay free of native CAD
dependencies.

:mod:`app.cad_worker.main` is the entry point. It is executed as::

    <worker-python> -m app.cad_worker.main <request.json> <response.json>

No CAD library is imported at module import time, so importing this package
costs nothing and is safe from the API's own interpreter.
"""
