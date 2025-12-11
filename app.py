@app.route('/api/payments', methods=['GET'])
def get_all_payments():
    try:
        payments = db.collection('payments').order_by(
            'timestamp', direction=firestore.Query.DESCENDING
        ).stream()

        data = []
        for payment in payments:
            p = payment.to_dict()

            business_doc = db.collection('businesses').document(p.get('slug', '')).get()
            business_name = business_doc.to_dict().get('name', 'Unknown') if business_doc.exists else 'Unknown'

            ts = p.get('timestamp')
            formatted_time = ts.strftime('%d %b %Y • %I:%M %p') if ts else 'N/A'

            unit_price = 0
            if p.get('credits', 0) > 0:
                unit_price = p.get('amount', 0) / p.get('credits', 1)

            data.append({
                'business_name': business_name,
                'slug': p.get('slug', ''),
                'credits': p.get('credits', 0),
                'amount': p.get('amount', 0),
                'unit_price': unit_price,
                'razorpay_payment_id': p.get('razorpay_payment_id', ''),
                'timestamp': formatted_time
            })

        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
