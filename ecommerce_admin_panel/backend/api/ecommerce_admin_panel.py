# ecommerce_admin_panel API
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
def get_products(request):
    products = [
        {'id': 1, 'name': 'Product 1', 'price': 10.99},
        {'id': 2, 'name': 'Product 2', 'price': 19.99}
    ]
    return JsonResponse(products, safe=False)

@csrf_exempt
def add_product(request):
    data = json.loads(request.body)
    product = {
        'id': data['id'],
        'name': data['name'],
        'price': data['price']
    }
    return JsonResponse(product, safe=False)