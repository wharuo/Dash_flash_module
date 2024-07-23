import pandas as pd
from flask import send_file

# Export traffic data
@server.route('/export/traffic')
@login_required
def export_traffic():
    analytics = initialize_analyticsreporting()
    response = get_report(analytics)
    data = parse_response(response)
    data.to_csv('traffic_data.csv', index=False)
    return send_file('traffic_data.csv', as_attachment=True)

# Export social media data
@server.route('/export/socialmedia')
@login_required
def export_socialmedia():
    data = asyncio.run(get_twitter_data())
    data.to_csv('social_media_data.csv', index=False)
    return send_file('social_media_data.csv', as_attachment=True)

# Export Facebook data
@server.route('/export/facebook')
@login_required
def export_facebook():
    data = get_facebook_data()
    data.to_csv('facebook_data.csv', index=False)
    return send_file('facebook_data.csv', as_attachment=True)

# Export Instagram data
@server.route('/export/instagram')
@login_required
def export_instagram():
    data = asyncio.run(get_instagram_data())
    data.to_csv('instagram_data.csv', index=False)
    return send_file('instagram_data.csv', as_attachment=True)
