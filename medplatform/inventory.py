"""Generate inventories from a disposable migrated DB and registered input models."""
import importlib
import json
from pathlib import Path
import tempfile

from . import __version__
from .database import Database
from .migrations import catalog, migrate

MODULES = ('s02_api', 's03_records', 's03_analytics', 's03_execution', 's04_api', 's05_api', 's05_draft_api', 's05_service_api',
           's05_feedback_api', 's05_peer_api', 's05_points_api', 's05_rewards_api')


def export(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        db = Database(Path(temp) / 'inventory.sqlite3')
        version = migrate(db, initialize=True)
        with db.connection(readonly=True) as conn:
            tables = []
            for name, ddl in conn.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall():
                quoted = '"' + name.replace('"', '""') + '"'
                tables.append(dict(name=name, ddl=ddl,
                    columns=[dict(r) for r in conn.execute('PRAGMA table_xinfo(' + quoted + ')')],
                    foreign_keys=[dict(r) for r in conn.execute('PRAGMA foreign_key_list(' + quoted + ')')],
                    indexes=[dict(r) for r in conn.execute('PRAGMA index_list(' + quoted + ')')]))
    routes = []
    for module in MODULES:
        for identifier, method, path, action, model in importlib.import_module('.' + module, __package__).ROUTES:
            routes.append(dict(id=identifier, method=method, path='/api/v1' + path, action=action,
                               owner_module=module, input_schema=model.model_json_schema() if model else None))
    # Foundation's two routes are directly registered in web.py.
    routes.extend([dict(id='foundation-health', method='GET', path='/api/v1/health', owner_module='web', input_schema=None),
                   dict(id='foundation-config', method='GET', path='/api/v1/config/status', owner_module='web', input_schema=None)])
    storage = dict(application=__version__, schema_version=f'{version:04d}', tables=tables,
                   migrations=[dict(version=f'{m.version:04d}', name=m.name, sha256=m.checksum) for m in catalog()])
    (directory / 'storage-schema.json').write_text(json.dumps(storage, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    (directory / 'interface-manifest.json').write_text(json.dumps(dict(application=__version__, routes=routes), ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    return dict(tables=len(tables), registered_routes=len(routes), schema_version=f'{version:04d}')
