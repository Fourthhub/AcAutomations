import datetime
import logging
import azure.functions as func
import requests
import json  # Importa el módulo json para procesar el cuerpo de la solicitudç
url = "https://api.holded.com/api/invoicing/v1/documents/invoice"


def determinarSerie(reserva):
    custom_fields = reserva["customFieldValues"]
    #Por defecto va a la serie Alojamientos
    facturas_value = "Alojamientos"
    for field in custom_fields:
        if field["customField"]["name"] == "Facturas":
            facturas_value = field["value"]
            break
    
    return facturas_value

#mapeo de nombres de series y su ID
parametro_a_id = {
    "Rocio": "65d9f06600a829a27305f066s",
    "Alojamientos": "65d9f0e90396551d79088219",
    "Efectivo": "62115e5292bee258e53a6756",
}


def crearFactura(reserva):

    now = datetime.datetime.now()
    timestamp = int(datetime.datetime.timestamp(now))
    serieFacturacion = parametro_a_id[determinarSerie(reserva)]
    payload = {
        "applyContactDefaults": True,
        "items": [
            {
                "tax": 21,
                "name": f"{reserva['listingName']} - {reserva['arrivalDate']} a {reserva['departureDate']}",
                "subtotal": str(reserva["totalPrice"]/1.21))
            }
        ],
        "currency": reserva["currency"],
        "date": timestamp,  # Uso de timestamp de la fecha de reserva
        "numSerieId": serieFacturacion,
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

        if 
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
        
