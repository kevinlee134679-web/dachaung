import re


class ModuleRegistry:
    def __init__(self):
        self.operations = {}
        self.routes = set()
        self.names = set()

    def register_operation(self, name, operation):
        if not isinstance(name, str) or not name or not callable(operation):
            raise ValueError("operation must have an explicit name and callable")
        if name in self.operations:
            raise ValueError("duplicate operation registration")
        self.operations[name] = operation

    def include_router(self, app, router):
        proposed = []
        names = set()
        existing = {
            (method, re.sub(r"\{[^}]+\}", "{}", route.path))
            for route in app.routes
            for method in (getattr(route, "methods", None) or ())
        }
        # Included routers may be lazy wrappers in FastAPI. Their registrations
        # are already in self.routes/self.names; inspect direct routes as well.
        existing_names = {
            getattr(route, "operation_id", None) or getattr(route, "name", None)
            for route in app.routes
        }
        for route in router.routes:
            if not getattr(route, "methods", None):
                raise ValueError("only explicit HTTP routes may be registered")
            name = route.operation_id or route.name
            if name in self.names or name in names or name in existing_names:
                raise ValueError("duplicate operation name")
            names.add(name)
            for method in route.methods:
                key = (method, re.sub(r"\{[^}]+\}", "{}", route.path))
                if key in self.routes or key in proposed or key in existing:
                    raise ValueError("duplicate method/path registration")
                proposed.append(key)
        app.include_router(router)
        self.routes.update(proposed)
        self.names.update(names)
