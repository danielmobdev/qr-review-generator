@app.route('/api/businesses/<slug>', methods=['DELETE'])
def delete_business(slug):
    try:
        db.collection('businesses').document(slug).delete()
        # Optionally delete QR file
        qr_path = f'static/qr_{slug}.png'
        if os.path.exists(qr_path):
            os.remove(qr_path)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
