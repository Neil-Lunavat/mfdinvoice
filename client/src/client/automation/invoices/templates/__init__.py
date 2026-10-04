"""Invoice formats, as data. Each module holds one template; `TEMPLATES` names them.

A second template is a second data module and a line here, not a change to the engine (`server.invoices.layout`).
"""

from client.automation.invoices.templates import tally

TEMPLATES = {"tally": tally.TEMPLATE}
NAMES = {"tally": "Tally standard print"}
