import logging
import facturacion
import azure.functions as func
import json  # Importa el módulo json para procesar el cuerpo de la solicitud

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    try:
        # Intenta obtener el cuerpo de la solicitud y convertirlo de JSON a un diccionario de Python
        req_body = req.get_json()
    except ValueError:
        # Si hay un error al interpretar el JSON, devuelve un error
        return func.HttpResponse(
            "Please send a valid JSON in the request bodddy.",
            status_code=400
        )
    else:
        # Genera la factura en base al la informacion de la req recibido
        try:
            facturacion.crearFactura(req_body)
        except Exception:
            return  func.HttpResponse(
            "Un error ha ocurrido al crear la factura.",
            status_code=400)

        
        return func.HttpResponse(
            f"Factura creada correctamente",
            status_code=200
        )
        
