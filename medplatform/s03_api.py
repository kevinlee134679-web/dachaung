"""Registered S03 routes using the existing same-origin request boundary."""
import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from .errors import AppError
from .migrations import status
from .s02_api import pairs, reject_constant


def router(modules, envelope):
    result = APIRouter()
    for module, service in modules:
        for card,method,path,action,schema in module.ROUTES:
            def endpoint(service=service, module=module, action=action, schema=schema, method=method):
                async def handle(request: Request):
                    await run_in_threadpool(status,service.db)
                    if action in {"provider_receipt", "fulfillment_receipt"}:
                        principal = getattr(request.state, "integration_principal", None)
                        if principal is None:
                            raise AppError(401, "AUTH_REQUIRED", "需使用独立的模拟服务方凭据")
                    else:
                        principal = service.auth.resolve(request.cookies.get('session'))
                    params = dict(request.path_params)
                    try:
                        if any(not 1<=len(value)<=128 for value in params.values()):
                            raise ValueError()
                        q = module.query_input(action,request.query_params.multi_items())
                        body = {}
                        if method != 'GET':
                            if request.headers.get('content-type','').split(';')[0]!='application/json':
                                raise AppError(415,'UNSUPPORTED_MEDIA_TYPE','此操作需要JSON请求')
                            raw = json.loads(await request.body(),object_pairs_hook=pairs,parse_constant=reject_constant)
                            body = schema.model_validate(raw).model_dump()
                        elif await request.body():
                            raise ValueError()
                    except (ValidationError,ValueError,TypeError,KeyError,OverflowError):
                        raise AppError(422,'VALIDATION_ERROR','请求字段、时区、窗口或格式不合法') from None
                    response = await run_in_threadpool(service.handle,action,principal,params,q,body,request.headers.get('Idempotency-Key'))
                    error = response.error
                    return JSONResponse(envelope(request,response.data,**({'code':error['code'],'message':error['message']} if error else {})),
                                        status_code=response.status,headers=response.headers)
                return handle
            result.add_api_route('/api/v1'+path,endpoint(),methods=[method],operation_id=card,name=card)
    return result
