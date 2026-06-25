import psycopg2

print("🔍 Проверяем подключение к PostgreSQL...")

# Пробуем подключиться к серверу (без конкретной БД)
try:
    conn = psycopg2.connect(
        host="localhost",
        port=5433,
        user="postgres",
        password="postgres123"  # ⚠️ Замените на пароль, который вы задали при установке!
    )
    print("✅ Сервер PostgreSQL работает! Подключение к 'postgres' успешно.")
    conn.close()
except Exception as e:
    print(f"❌ Ошибка подключения к серверу: {e}")
    print("\n💡 Возможные причины:")
    print("   1. Служба PostgreSQL не запущена (проверьте services.msc)")
    print("   2. Неверный пароль от пользователя 'postgres'")
    print("   3. PostgreSQL слушает другой порт (не 5432)")
    exit(1)

# Пробуем подключиться к нашей БД
try:
    conn = psycopg2.connect(
        host="localhost",
        port=5433,
        user="vkr_user",
        password="vkr_password",
        database="vkr_db"
    )
    print("✅ База данных 'vkr_db' существует и доступна!")
    conn.close()
except Exception as e:
    print(f"❌ Ошибка подключения к vkr_db: {e}")
    print("\n💡 Возможные причины:")
    print("   1. База 'vkr_db' не создана")
    print("   2. Пользователь 'vkr_user' не создан")
    print("   3. Неверный пароль 'vkr_password'")