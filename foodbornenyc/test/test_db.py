"""
Generates a small test DB by recreating the tables and copying over a few entries.
"""
from sqlalchemy.orm.session import make_transient, make_transient_to_detached
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.expression import text

import foodbornenyc.models.models as models
from foodbornenyc.models.businesses import Business, business_category_table
from foodbornenyc.models.documents import YelpReview, Tweet, Document
from foodbornenyc.models.users import TwitterUser
from foodbornenyc.models.locations import Location
from foodbornenyc.models.metadata import metadata

from foodbornenyc.util.util import sec_to_hms, get_logger
logger = get_logger(__name__, level="INFO")

test_config = {
    'user': 'johnnybananas',
    'password': 'placeholder_password',
    'dbhost': 'toy.db',
    'dbbackend':'sqlite'
}


def get_db_session(**kwargs):
    return models.get_db_session(config=test_config, **kwargs)

def reset_test_db():
    """ Drops all tables and recreates them. To be done once per schema change
    to update toy.db. """
    logger.info("Resetting all tables in %s", test_config['dbhost'])
    models.drop_all_tables(test_config)
    models.setup_db(test_config)

def clear_tables():
    """ Clears the tables without dropping them. For use in test setup. """
    import contextlib
    with contextlib.closing(models.get_db_engine(test_config).connect()) as con:
        trans = con.begin()
        for table in reversed(metadata.sorted_tables):
            con.execute(table.delete())
        trans.commit()

def copy_tables():
    """ Copies a few items from each table into a test database

    Should not be called in the same session after reset_test_db(); you will get
    a mapper error for some reason. Instead, call reset_test_db(), then close
    the python session, then, in a new session, call copy_tables(), to update
    the tables for a schema change. """
    toy = get_db_session()
    db = models.get_db_session()

    logger.info("Populating test tables")

    businesses = db.query(Business).order_by(Business.id)[0:5]
    locations = [b.location for b in businesses]
    # [b.categories ...] is a list of lists, so we need a little more processing
    categories = set().union(*[b.categories for b in businesses])

    tweets = db.query(Tweet).order_by(Tweet.id)[0:5]
    reviews = []
    for b in businesses:
        reviews.extend(
            db.query(YelpReview).filter(YelpReview.business_id == b.id)[0:5]
        )
    documents = [r.document for r in reviews] + [t.document for t in tweets]
    doc_assoc = [r.document_rel for r in reviews] + \
                [t.document_rel for t in tweets]

    tables = [businesses, locations, categories, reviews, tweets, \
              documents, doc_assoc]

    # detach all objects from db session before putting them in toy
    for t in tables:
        for obj in t: make_transient(obj)

    # only after *everything* is transient do we add anything
    for t in tables: toy.add_all(t)

    # in addition we add the junction table for business categories
    b_ids = [b.id for b in businesses]
    business_cat = db.execute(business_category_table.select().
            where(business_category_table.c.business_id.in_(
                [b.id for b in businesses]
            )))

    for row in business_cat:
        toy.execute(business_category_table.insert(), row)

    toy.commit()

if __name__ == "__main__":
    main()
