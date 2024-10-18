import json
import boto3 # type: ignore

# Inicialización de clientes de AWS para S3, Rekognition y Translate
s3 = boto3.client('s3')
rekognition = boto3.client('rekognition')
translate = boto3.client('translate')

# Nombre del bucket donde se almacenan las imágenes
BUCKET_NAME = 'rekognition-images-bucket-pi-virginia'  # Asegúrate de que esté en la región correcta

# Función para obtener la imagen más reciente del bucket
def get_latest_image_key(bucket_name):
    response = s3.list_objects_v2(Bucket=bucket_name)
    if 'Contents' in response:
        sorted_objects = sorted(response['Contents'], key=lambda obj: obj['LastModified'], reverse=True)
        latest_image_key = sorted_objects[0]['Key']
        return latest_image_key
    else:
        raise Exception("No se encontraron objetos en el bucket.")

# Función principal que maneja el evento Lambda
def lambda_handler(event, context):
    print("Evento recibido de Lex: ", event)
    
    try:
        # Obtener información del evento de Lex
        invocation_source = event['invocationSource']  # Fuente de invocación (DialogCodeHook o FulfillmentCodeHook)
        intent_name = event['sessionState']['intent']['name']  # Nombre del intent
        slots = event['sessionState']['intent']['slots'] if 'slots' in event['sessionState']['intent'] else {}

        # 1. Proceso del DialogCodeHook (se usa cuando está en progreso)
        if invocation_source == 'DialogCodeHook':
            return {
                'sessionState': {
                    'dialogAction': {
                        'type': 'Delegate',
                    },
                    'intent': {
                        'name': event['sessionState']['intent']['name'],
                        'slots': slots,
                        'state': 'InProgress'
                    }
                }
            }

        # 2. Proceso de FulfillmentCodeHook (cuando el intent ha llegado a fulfillment)
        elif invocation_source == 'FulfillmentCodeHook':
            user_input = event['inputTranscript']  # Texto ingresado por el usuario
            print(f"Entrada del usuario: {user_input}")
            
            # Obtener la última imagen subida al bucket
            image_key = get_latest_image_key(BUCKET_NAME)
            print(f"Procesando la imagen más reciente: {image_key}")

            # 2.1. Si el intent es 'TextExtractor' se usa detect_text para extraer texto
            if intent_name == "TextExtractor":
                response_text = rekognition.detect_text(
                    Image={
                        'S3Object': {
                            'Bucket': BUCKET_NAME,
                            'Name': image_key
                        }
                    }
                )
                # Extraer el texto detectado
                text_detections = response_text['TextDetections']
                extracted_text = ' '.join([text['DetectedText'] for text in text_detections if text['Type'] == 'LINE'])
                print(f"Texto detectado: {extracted_text}")
                
                # Devolver el mensaje con el texto extraído
                message = f"La imagen dice: {extracted_text}"

            # 2.2. Si el intent es 'AnalyzeImageIntent' se usa detect_labels para analizar objetos
            elif intent_name == "AnalyzeImageIntent":
                response_rekognition = rekognition.detect_labels(
                    Image={
                        'S3Object': {
                            'Bucket': BUCKET_NAME,
                            'Name': image_key
                        }
                    },
                    MaxLabels=10
                )
                labels = response_rekognition['Labels']
                analysis_result = ', '.join([label['Name'] for label in labels])
                print("Resultado del análisis: ", analysis_result)

                # Traducir el resultado al español
                translated_result = translate.translate_text(
                    Text=analysis_result,
                    SourceLanguageCode='en',
                    TargetLanguageCode='es'
                )
                print("Traducción del resultado: ", translated_result['TranslatedText'])
                
                # Mensaje con los resultados traducidos
                message = f"He analizado la imagen y los resultados son: {translated_result['TranslatedText']}"

            # 2.3. Si el intent es 'WhatObjectsIntent', también se usa detect_labels
            elif intent_name == "WhatObjectsIntent":
                response_rekognition = rekognition.detect_labels(
                    Image={
                        'S3Object': {
                            'Bucket': BUCKET_NAME,
                            'Name': image_key
                        }
                    },
                    MaxLabels=10
                )
                labels = response_rekognition['Labels']
                analysis_result = ', '.join([label['Name'] for label in labels])
                print("Resultado del análisis: ", analysis_result)

                # Traducir el resultado al español
                translated_result = translate.translate_text(
                    Text=analysis_result,
                    SourceLanguageCode='en',
                    TargetLanguageCode='es'
                )
                print("Traducción del resultado: ", translated_result['TranslatedText'])

                # Mensaje con los objetos detectados traducidos
                message = f"Los objetos detectados en la imagen son: {translated_result['TranslatedText']}"

            # Responder a Lex con el mensaje correspondiente
            return {
                'sessionState': {
                    'dialogAction': {
                        'type': 'Close',
                        'fulfillmentState': 'Fulfilled'
                    },
                    'intent': {
                        'name': event['sessionState']['intent']['name'],
                        'slots': slots,
                        'state': 'Fulfilled'
                    }
                },
                'messages': [
                    {
                        'contentType': 'PlainText',
                        'content': message
                    }
                ]
            }

        # Si no es el evento esperado, devolver un error
        else:
            return {
                'sessionState': {
                    'dialogAction': {
                        'type': 'Close',
                        'fulfillmentState': 'Failed'
                    },
                    'intent': {
                        'name': event['sessionState']['intent']['name'],
                        'slots': slots,
                        'state': 'Failed'
                    }
                },
                'messages': [
                    {
                        'contentType': 'PlainText',
                        'content': "No se recibió el evento esperado de Lex."
                    }
                ]
            }
    
    # 3. Manejo de errores
    except Exception as e:
        print(f"Error procesando la imagen: {str(e)}")
        return {
            'sessionState': {
                'dialogAction': {
                    'type': 'Close',
                    'fulfillmentState': 'Failed'
                },
                'intent': {
                    'name': event['sessionState']['intent']['name'],
                    'slots': slots,
                    'state': 'Failed'
                }
            },
            'messages': [
                {
                    'contentType': 'PlainText',
                    'content': f"Hubo un error procesando la imagen: {str(e)}"
                }
            ]
        }
