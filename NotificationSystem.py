# Notification system
notifications = []

def add_notification(message):
    notifications.append({'message': message, 'seen': False})

def get_notifications():
    return [n for n in notifications if not n['seen']]

def mark_notifications_as_seen():
    for n in notifications:
        n['seen'] = True

@app.route('/notifications')
@login_required
def notifications():
    user_notifications = get_notifications()
    mark_notifications_as_seen()
    return render_template('notifications.html', notifications=user_notifications)
