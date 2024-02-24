import datetime
import logging
from holdedModule import crearFactura
import azure.functions as func
import json  # Importa el módulo json para procesar el cuerpo de la solicitud

def crearFactura(reserva):
    # Convertir la fecha de reserva a timestamp
    
    now = datetime.datetime.now()
    timestamp = int(datetime.datetime.timestamp(now))

    payload = {
        "applyContactDefaults": True,
        "items": [
            {
                "name": f"{reserva['listingName']} - {reserva['arrivalDate']} a {reserva['departureDate']}",
                "subtotal": str(reserva["totalPrice"])
            }
        ],
        "currency": reserva["currency"],
        "date": timestamp,  # Uso de timestamp de la fecha de reserva
        #"numSerieId": "Rocio",
        "contactName": reserva["guestName"]  # Uso del nombre del huésped
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "key": "260f9570fed89b95c28916dee27bc684"
    }

    response = requests.post(url, json=payload, headers=headers)
    return response.status_code

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
            crearFactura(req_body)
        except Exception as e:
            return  func.HttpResponse(str(e)
            ,
            status_code=400)

        
        return func.HttpResponse(
            f"Factura creada correctamente",
            status_code=200
        )
        
