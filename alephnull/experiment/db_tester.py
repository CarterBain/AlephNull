import alephnull.experiment.dummy_futures_data_generator as dat
import alephnull.experiment.sqlite_interface as sq
import random

def test_db():
    fdb = sq.FuturesDB("temp" + str(random.randint(0,1000000)) + ".db")
    fdb.initialize_tables()
    fdb.insert_dict(dat.create_dummy_universe_dict())
    
    result = fdb.get_all_timestamps()
    return (fdb, result)