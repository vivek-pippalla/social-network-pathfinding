from neo4j import Driver


def _create_account_and_user(
    tx,
    user_id: str,
    name: str,
    email: str,
    email_normalized: str,
    password_hash: str,
) -> dict:
    record = tx.run(
        """
        CREATE (u:User {
            id: $user_id,
            name: $name,
            name_lower: toLower($name),
            source: 'app',
            created_at: datetime()
        })
        CREATE (a:Account {
            email: $email,
            email_normalized: $email_normalized,
            password_hash: $password_hash,
            created_at: datetime()
        })
        CREATE (a)-[:OWNS]->(u)
        RETURN u.id AS id, u.name AS name, u.source AS source, a.email AS email
        """,
        user_id=user_id,
        name=name,
        email=email,
        email_normalized=email_normalized,
        password_hash=password_hash,
    ).single()
    return dict(record)


def create_account_and_user(
    driver: Driver,
    *,
    user_id: str,
    name: str,
    email: str,
    email_normalized: str,
    password_hash: str,
) -> dict:
    with driver.session() as session:
        return session.execute_write(
            _create_account_and_user,
            user_id,
            name,
            email,
            email_normalized,
            password_hash,
        )


def get_account_by_email(driver: Driver, email_normalized: str) -> dict | None:
    with driver.session() as session:
        record = session.execute_read(
            lambda tx: tx.run(
                """
                MATCH (a:Account {email_normalized: $email_normalized})-[:OWNS]->(u:User)
                RETURN a.email AS email, a.password_hash AS password_hash, u.id AS user_id
                """,
                email_normalized=email_normalized,
            ).single()
        )
    return dict(record) if record else None


def update_password_hash(driver: Driver, user_id: str, password_hash: str) -> None:
    with driver.session() as session:
        session.execute_write(
            lambda tx: tx.run(
                """
                MATCH (a:Account)-[:OWNS]->(:User {id: $user_id})
                SET a.password_hash = $password_hash
                RETURN a.email_normalized AS email_normalized
                """,
                user_id=user_id,
                password_hash=password_hash,
            ).consume()
        )
