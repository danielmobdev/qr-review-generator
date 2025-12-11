@app.route('/api/payments', methods=['GET'])
def get_all_payments():
    try:
        payments = db.collection('payments').order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
        data = []
        for payment in payments:
            p = payment.to_dict()
            # Get business name using slug
            business_doc = db.collection('businesses').document(p.get('slug', '')).get()
            business_name = business_doc.to_dict().get('name', 'Unknown') if business_doc.exists else 'Unknown'
            
            # Format timestamp
            timestamp = p.get('timestamp')
            if timestamp:
                formatted_time = timestamp.strftime('%d %b %Y • %I:%M %p')
            else:
                formatted_time = 'N/A'
            
            data.append({
                'business_name': business_name,
                'slug': p.get('slug', ''),
                'credits': p.get('credits', 0),
                'amount': p.get('amount', 0),
                'unit_price': p.get('unit_price', 0),
                'razorpay_payment_id': p.get('razorpay_payment_id', ''),
                'timestamp': formatted_time
            })
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
