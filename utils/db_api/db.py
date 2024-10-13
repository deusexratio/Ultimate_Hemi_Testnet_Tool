from sqlalchemy import create_engine, text, update, and_
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session


class DB:
    def __init__(self, db_url: str, **kwargs):
        """
        Initializes a class.

        :param str db_url: a URL containing all the necessary parameters to connect to a DB
        """
        self.db_url = db_url
        self.engine = create_engine(self.db_url, **kwargs)
        self.Base = None
        self.s: Session = Session(bind=self.engine)
        self.conn = self.engine.connect()
        # self.update = update()

    def create_tables(self, base):
        """
        Creates tables.

        :param base: a base class for declarative class definitions
        """
        self.Base = base
        self.Base.metadata.create_all(self.engine)

    def all(self, entities=None, *criterion, stmt=None) -> list:
        """
        Fetches all rows.

        :param entities: an ORM entity
        :param stmt: stmt
        :param criterion: criterion for rows filtering
        :return list: the list of rows
        """
        if stmt is not None:
            return list(self.s.scalars(stmt).all())

        if entities and criterion:
            return self.s.query(entities).filter(*criterion).all()

        if entities:
            return self.s.query(entities).all()

        return []

    def one(self, entities=None, *criterion, stmt=None, from_the_end: bool = False):
        """
        Fetches one row.

        :param entities: an ORM entity
        :param stmt: stmt
        :param criterion: criterion for rows filtering
        :param from_the_end: get the row from the end
        :return list: found row or None
        """
        if entities and criterion:
            rows = self.all(entities, *criterion)
        else:
            rows = self.all(stmt=stmt)

        if rows:
            if from_the_end:
                return rows[-1]

            return rows[0]

        return None

    def execute(self, query, *args):
        """
        Executes SQL query.

        :param query: the query
        :param args: any additional arguments
        """
        result = self.conn.execute(text(query), *args)
        self.commit()
        return result

    def commit(self):
        """
        Commits changes.
        """
        try:
            self.s.commit()

        except DatabaseError:
            self.s.rollback()

    def insert(self, row: object | list[object]):
        """
        Inserts rows.

        :param Union[object, list[object]] row: an ORM entity or list of entities
        """
        if isinstance(row, list):
            self.s.add_all(row)

        elif isinstance(row, object):
            self.s.add(row)

        else:
            raise ValueError('Wrong type!')

        self.commit()

    def update(self, entities, columns: object | list[object], now_value, future_value, *args):
        """
        Updates specified columns with args

        :param entities: specify which table needs to be updated
        :param Union[object, list[object]] columns: columns which values have to be changed
        :param args: any additional arguments
        :param now_value
        :param future_value
        """
        if isinstance(columns, list):
            for column in columns:
                stmt = update(table=entities).where(column == now_value).values(future_value)
                self.s.query(stmt)

            # self.s.add_all(columns)
            # update(table=self.s.add_all(columns))
            # update(columns)

        elif isinstance(columns, object):
            stmt = update(table=entities).where(columns == now_value).values(future_value)
            self.s.query(stmt)

        else:
            raise ValueError('Wrong entities type ot smth')

        # stmt = (
        #     update(table=entities).filter(columns).values()
        #
        # )
        self.s.commit()
