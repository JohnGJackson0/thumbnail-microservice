from io import BytesIO
import json
import boto3
import os
import uuid
from datetime import datetime
# import resolved using layer
from PIL import Image, ImageOps

# get all buckets in the s3 storage
# s3 is cloud 
s3 = boto3.client('s3')
# use env variables in serverless.yml
# to specify what thumbnail resizes to from
# original image
size = int(os.environ['THUMBNAIL_SIZE'])
dbtable = str(os.environ['DYNAMODB_TABLE'])
dynamodb = boto3.resource(
    'dynamodb', region_name=str(os.environ['REGION_NAME'])
)

def s3_thumbnail_generator(event, context):
    print('EVENT:::', event)

    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']
    img_size = event['Records'][0]['s3']['object']['size']

    def get_s3_image(bucket, key):
        response = s3.get_object(Bucket=bucket, Key=key)
        imageContent = response['Body'].read()
        file = BytesIO(imageContent)
        img = Image.open(file)
        return img

    def image_to_thumbnail(image):
        return ImageOps.fit(image, (size, size), Image.ANTIALIAS)

    def new_filename(key):
        key_split = key.rsplit('.', 1)
        return key_split[0] + '_thumbnail.png'
    
    def save_thumbnail_meta_to_dynamo(url_path, img_size):
        table = dynamodb.Table(dbtable)
        response = table.put_item(
            Item = {
                'id': str(uuid.uuid4()),
                'url': str(url_path),
                'originalSizeKb': str(img_size),
                'createdAt': str(datetime.now()),
                'updatedAt' : str(datetime.now())
            }
        )

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(response)
        }

    def upload_to_s3(bucket, key, image): 
        out_thumbnail = BytesIO()
        image.save(out_thumbnail, 'PNG')
        out_thumbnail.seek(0)
        response = s3.put_object(
            ACL='public-read',
            Body=out_thumbnail, 
            Bucket=bucket, 
            ContentType='image/png',
            Key=key
        )

        print('response in upload to s3', response)

        body = {
            "message": "Go Serverless v3.0! Your function executed successfully!",
            "input": event,
        }

        return {"statusCode": 200, "body": json.dumps(body)}

    if(not key.endswith('_thumbnail.png')):
        image = get_s3_image(bucket, key)
        thumbnail = image_to_thumbnail(image)
        thumbnail_key = new_filename(key)
        response = upload_to_s3(bucket, thumbnail_key, thumbnail)

        # this wont age well
        url = 'https://thumbnail-service.s3.amazonaws.com/'+thumbnail_key;

        save_thumbnail_meta_to_dynamo(url_path=url, img_size=img_size)

        return response
