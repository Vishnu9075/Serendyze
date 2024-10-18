from pymongo import MongoClient
from kafka import KafkaConsumer
import json

client = MongoClient("mongodb+srv://vishnualle8:B2jla3A25J0axCG0@cluster0.ualp9.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = client.tracking
collection = db.user_interactions

consumer = KafkaConsumer(
    'user_clicks',
    bootstrap_servers=['localhost:9092'],
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    group_id='tracking-consumer-group',
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

def consume_and_store():
    print("Starting Kafka Consumer...")
    for message in consumer:
        print(f"Consumed message: {message.value}")

        if isinstance(message.value, dict):
            username = message.value['username']
            user_id = message.value['user_id']
            link_karma = message.value['link_karma']
            comment_karma = message.value['comment_karma']
            total_karma = message.value['total_karma']
            created_utc = message.value['created_utc']
            interaction_data = message.value['interactions'][0]

            existing_user = collection.find_one({"username": username, "user_id": user_id})

            if existing_user:
                collection.update_one(
                    {"username": username, "user_id": user_id},
                    {"$push": {"interactions": interaction_data}}
                )
                print(f"Updated existing user with interaction: {interaction_data}")
            else:
                new_user = {
                    "username": username,
                    "user_id": user_id,
                    "link_karma": link_karma,
                    "comment_karma": comment_karma,
                    "total_karma": total_karma,
                    "created_utc": created_utc,
                    "interactions": [interaction_data]
                }
                collection.insert_one(new_user)
                print(f"Inserted new user with first interaction: {new_user}")
        else:
            print(f"Invalid message format, skipping: {message.value}")

if __name__ == '__main__':
    consume_and_store()
