import sys
import os
sys.path.insert(0, r"c:\Users\sriva_3b9ej2a\OneDrive\Documents\projects\university-query-system")

from models.base import SessionLocal
from models.ticket import Ticket, TicketStatus
from models.user import User

db = SessionLocal()
user = db.query(User).filter(User.email == "carol@greenfield.edu").first()
if user:
    print(f"Found user: {user.name} (ID: {user.id})")
    tickets = db.query(Ticket).filter(Ticket.student_id == user.id).all()
    for t in tickets:
        print(f"Ticket #{t.id}: {t.title} | status: {t.status} | feedback: {t.feedback}")
        if not t.feedback:
            t.status = TicketStatus.resolved
            print(f"-> Resolving Ticket #{t.id}")
    db.commit()
else:
    print("Carol Student not found.")
db.close()
