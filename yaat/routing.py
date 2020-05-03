from collections import OrderedDict
from enum import Enum
from parse import parse
import typing

from yaat.constants import HTTP_METHODS


class RouteTypes(Enum):
    HTTP = 1  # http route
    STATIC = 2  # static handler route
    WEBSOCKET = 3  # websocket route


class Route:
    def __init__(
        self,
        route_type: RouteTypes,
        path: str,
        handler: typing.Callable,
        methods: typing.List[str] = None,
    ):
        self.route_type = route_type
        self.path = path
        self.handler = handler
        self.methods = methods if methods else HTTP_METHODS

    @property
    def type(self) -> RouteTypes:
        return self.route_type

    @property
    def methods(self) -> typing.List[str]:
        return self.__methods

    @methods.setter
    def methods(self, methods: typing.List[str]):
        # make sure all HTTP methods are upper
        self.__methods = [method.upper() for method in methods]

    def is_valid_method(self, method: str) -> bool:
        return method.upper() in self.methods


class Router:
    def __init__(self):
        self.routes = OrderedDict()
        self.__paths = []

    @property
    def paths(self):
        self.__paths = []  # reset before loading paths
        return self._get_paths()

    def _get_paths(
        self, routes: OrderedDict = None, prev_path: str = None
    ) -> typing.List[str]:
        """
        Method to traverse through routes and sub router inside its to get all handler paths.
        """
        if not routes:
            routes = self.routes

        for path, router in routes.items():
            if isinstance(router, Route):
                fullpath = (
                    f"{prev_path}{router.path}" if prev_path else router.path
                )
                self.__paths.append(fullpath)
            else:
                self._get_paths(router.routes, path)

        return self.__paths

    def route(
        self, path: str, methods: typing.List[str] = None
    ) -> typing.Callable:
        def wrapper(handler):
            self.add_route(path=path, handler=handler, methods=methods)
            return handler

        return wrapper

    def add_route(
        self,
        path: str,
        handler: typing.Callable,
        methods: typing.List[str] = None,
        is_static: bool = False,
    ):
        assert path not in self.paths, f"Route {path}, already exists"
        route_type = RouteTypes.STATIC if is_static else RouteTypes.HTTP
        path = self._clean_path(path)
        self.routes[path] = Route(
            route_type=route_type, path=path, handler=handler, methods=methods,
        )

    def websocket_route(self, path: str) -> typing.Callable:
        def wrapper(handler):
            self.add_websocket_route(path=path)
            return handler

        return wrapper

    def add_websocket_route(self, path: str, handler: typing.Callable):
        assert path not in self.paths, f"Route {path}, already exists"
        path = self._clean_path(path)
        self.routes[path] = Route(
            route_type=RouteTypes.WEBSOCKET, path=path, handler=handler
        )

    def mount(self, router: typing.Callable, prefix: str):
        """Mount another router"""
        assert (
            prefix not in self.routes.keys()
        ), f"Route with {prefix}, already exists"
        prefix = self._clean_path(prefix)
        self.routes[prefix] = router

    def get_route(
        self,
        *,
        request_path: str,
        prev_path: str = None,
        routes: OrderedDict = None,
    ) -> (Route, typing.Dict[str, typing.Any]):
        # if not given, use self
        if not routes:
            routes = self.routes

        for path, router in routes.items():
            # if route instance, just loop and search
            if isinstance(router, Route):
                route = router

                # for static routing, use different methods for route comparison
                if route.type == RouteTypes.STATIC:
                    return route, {"router_path": prev_path}

                parse_result = parse(route.path, request_path)
                print(request_path)
                if parse_result is not None:
                    return route, parse_result.named

            # else, router itself
            # Type of router
            #   - Sub Application
            #   - Static Files Handler
            else:
                directories = self._path_to_directories(request_path)
                first_directory = directories[0]

                # if != 1,means has multiple sub directory other than /
                # and if first directory not equal to router's path means
                # the requested url is not for the current router
                if len(directories) != 1 and first_directory != path:
                    continue

                # reconstruct previous path for next router
                if prev_path and first_directory != "/":
                    prev_path = f"{prev_path}{first_directory}"
                elif not prev_path and len(directories) == 1:
                    # first sub directory, so previous should be root /
                    prev_path = "/"
                else:
                    prev_path = first_directory

                # request path for next router would be all sub directories
                # below the current one
                next_request_path = self._directories_to_path(directories[1:])

                # search in sub router, if route is found return
                # else continue
                route, kwargs = self.get_route(
                    request_path=next_request_path,
                    prev_path=prev_path,
                    routes=router.routes,
                )
                if route:
                    return route, kwargs

        return None, None

    def _clean_path(self, path: str) -> str:
        if path == "/":
            return path
        if not path.startswith("/"):
            path = f"/{path}"
        if path.endswith("/"):
            path = path[:-1]
        return path

    def _path_to_directories(self, path: str) -> typing.List[str]:
        if path == "/":
            return ["/"]
        return [f"/{p}" for p in path.split("/") if p != ""]

    def _directories_to_path(self, directories: typing.List[str]) -> str:
        url = "".join(directories)
        if not url.startswith("/"):
            return f"/{url}"
        return url
