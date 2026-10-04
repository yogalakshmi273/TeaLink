from app import app
from models import db, User, Product, DeptYearPolicy

def seed_db():
    with app.app_context():
        # Create database tables if they do not exist
        db.create_all()
        
        # 1. Seed Admin User
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print("Seeding admin user...")
            admin = User(
                username='admin',
                name='DBCY Admin Administrator',
                role='admin',
                status='approved'
            )
            admin.set_password('admin123')
            db.session.add(admin)
        else:
            admin.set_password('admin123')



        # 3. Seed Department & Year Password Policies
        policies_data = [
            {'department': 'Computer Science', 'year': '3rd Year', 'allow': True, 'notes': 'Self-service password change enabled'},
            {'department': 'Computer Science', 'year': '2nd Year', 'allow': True, 'notes': 'Self-service password change enabled'},
            {'department': 'Computer Science', 'year': '1st Year', 'allow': True, 'notes': 'Self-service password change enabled'},
            {'department': 'Mathematics', 'year': '1st Year', 'allow': False, 'notes': 'Password change requires Admin approval'},
            {'department': 'Mathematics', 'year': '2nd Year', 'allow': True, 'notes': 'Self-service password change enabled'},
            {'department': 'English Literature', 'year': '3rd Year', 'allow': True, 'notes': 'Self-service password change enabled'},
            {'department': 'Commerce', 'year': '3rd Year', 'allow': True, 'notes': 'Self-service password change enabled'},
            {'department': 'Information Technology', 'year': '2nd Year', 'allow': True, 'notes': 'Self-service password change enabled'},
        ]

        for p_data in policies_data:
            pol = DeptYearPolicy.query.filter_by(department=p_data['department'], year=p_data['year']).first()
            if not pol:
                pol = DeptYearPolicy(
                    department=p_data['department'],
                    year=p_data['year'],
                    allow_password_change=p_data['allow'],
                    notes=p_data['notes']
                )
                db.session.add(pol)

        # 4. Seed DBCY Campus Teatime Products
        if Product.query.count() == 0:
            print("Seeding DBCY Campus Teatime menu items...")
            products = [
                Product(name='DBCY Special Masala Chai', price=12.00, category='HOT DRINKS', description='Rich spiced brewed tea with fresh ginger & cardamom', available=True),
                Product(name='Hot Filter Coffee', price=15.00, category='HOT DRINKS', description='Traditional South Indian filter coffee brew', available=True),
                Product(name='Cardamom Tea', price=12.00, category='HOT DRINKS', description='Aromatic cardamom infused milk tea', available=True),
                Product(name='Lemon Honey Tea', price=15.00, category='HOT DRINKS', description='Refreshing hot tea with lemon juice & honey', available=True),
                Product(name='Green Tea', price=15.00, category='HOT DRINKS', description='Healthy antioxidant green tea', available=True),
                Product(name='Iced Cold Coffee', price=40.00, category='COLD DRINKS', description='Chilled blended coffee with chocolate drizzle', available=True),
                Product(name='Cold Rose Milk', price=30.00, category='COLD DRINKS', description='Chilled fragrant rose milk shake', available=True),
                Product(name='Badam Milk', price=25.00, category='COLD DRINKS', description='Nutritious almond saffron milk served cold', available=True),
                Product(name='Crispy Veg Samosa (2 Pcs)', price=15.00, category='SNACKS', description='Crispy golden pastry stuffed with spiced potatoes', available=True),
                Product(name='Egg Puff', price=20.00, category='SNACKS', description='Flaky puff pastry stuffed with spiced boiled egg', available=True),
                Product(name='Crispy Veg Puff', price=15.00, category='SNACKS', description='Flaky puff pastry filled with spiced vegetables', available=True),
                Product(name='Paneer Cutlet', price=25.00, category='SNACKS', description='Golden pan-fried paneer cutlet with mint chutney', available=True),
                Product(name='Hot Cheese Maggi', price=35.00, category='SNACKS', description='Steaming hot Maggi noodles topped with melted cheese', available=True),
                Product(name='Cream Roll', price=15.00, category='BAKERY', description='Sweet flaky pastry roll filled with vanilla cream', available=True),
                Product(name='Chocolate Brownie', price=35.00, category='BAKERY', description='Fudgy rich chocolate brownie', available=True),
                Product(name='Butter Biscuits Pack', price=10.00, category='BAKERY', description='Crispy handmade bakery butter cookies', available=True),
                Product(name='Campus Teatime Combo (Tea + Samosa)', price=25.00, category='COMBOS', description='1 Masala Chai + 2 Crispy Veg Samosas combo deal', available=True),
            ]
            for p in products:
                db.session.add(p)

        db.session.commit()
        print("Database seeding completed successfully for DBCY Campus Teatime!")

if __name__ == '__main__':
    seed_db()

