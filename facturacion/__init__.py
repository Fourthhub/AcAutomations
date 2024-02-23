import logging
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
        # Extrae el listingName y la arrivalDate del cuerpo de la solicitud
        listing_name = req_body.get('listingName')
        arrival_date = req_body.get('arrivalDate')

        if listing_name and arrival_date:
            # Si ambos valores están presentes, devuelve una respuesta personalizada
            return func.HttpResponse(
                f"Received listing name: {listing_name} with arrival date: {arrival_date}.",
                status_code=200
            )
        else:
            # Si falta alguno de los valores, indica qué es necesario
            return func.HttpResponse(
                "Please ensure both 'listingName' and 'arrivalDate' are included in the request body.",
                status_code=400
            )
