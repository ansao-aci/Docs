from pyaci import Node, options, filters
import argparse
from argparse import RawTextHelpFormatter
import getpass


desc="""
python find_n_purge.py -delete 

1. Use delete option to  delete stale entries.
---> python find_n_purge.py -delete

2. Use without delete option, to show the stale entries
---> python find_n_purge.py -list

"""

def parse_args():
    parser = argparse.ArgumentParser(description=desc, formatter_class=RawTextHelpFormatter)
    parser.add_argument("-delete", action="store_true", dest="delete_option",
                        help="delete stale entries")
    parser.add_argument("-list", action="store_true", dest="list_option",
                        help="list stale entries")
    parser.add_argument('-leaf_ip','--list', nargs='+', help='<Required>: list of leaf IPs', required=True)
    parser.add_argument("-user", "--user", type=str, required=True)
    parser.add_argument("-password", "--password", type=str, required=False)

    args = parser.parse_args()

    if args.password is None:
            args.password = getpass.getpass('Enter {} password for leaf nodes access: '.format(
                args.user))

    if args.delete_option:
        print("\n\n Warning !!! This script will delete all stale null-mac IDEp entries.\n\n")
        input("Press Enter to continue...")
    if args.list_option:
        print("Just listing all the stale null-mac IDEp entries")

    return args

args = parse_args()

leaf_skipped=[]
user = args.user
password = args.password

for leaf_ip in args.list:
    leaf1 = "https://" + leaf_ip
    print("\n\n--------------------Processing " + leaf_ip + "\n\n")

    leaf = Node(leaf1)
    
    try:
        leaf.methods.Login(user, password).POST()
    except:
        leaf_skipped.append(leaf_ip)
        print("Exception occured while trying to login " + leaf_ip)
        continue
    
    IDEp = leaf.mit.topSystem().GET(**options.subtreeClass('opflexIDEp') &
                                    options.filter(filters.Eq('opflexIDEp.mac', '00:00:00:00:00:00')))
    
    EpPDset = set()
    EpPD = leaf.mit.compUni().compProv('OpenStack').GET(**options.subtreeClass('compEpPD'))
    
    print("--------------------Collected all eppds------------------------------.\n\n")
    for eppd in EpPD:
       EpPDset.add(eppd.Dn)
    
    deleted = 0
    for idep in IDEp:   
        domName = idep.__dict__['_properties']['domName']
        ctrlrName = idep.__dict__['_properties']['ctrlrName']
        print("--------------------checking IDEp: -------- " + idep.Dn)
    
        eppd = leaf.mit.compUni().compProv('OpenStack').compCtrlr(domName, ctrlrName).compEpPD(idep.__dict__['_properties']['epgPKey'])    
        if eppd.Dn not in EpPDset:
            print("--------------------stale found------------------------------: \n" + idep.Dn)
            print("--------------------No EpPD found for ------------------------------: \n" + eppd.Dn)
            if args.delete_option:
                result = leaf.mit.FromDn(idep.Dn).GET()
                result[0].DELETE()
                deleted = deleted + 1
                print("--------------------deleted IDep------------------------------: \n" + idep.Dn + "\n\n")
        else:
            print('--------------------found eppd------------------------------: \n' + eppd.Dn + "\n\n")
    
    if deleted == 0:
        print("--------------------No stale null-mac IDEp deleted in " + leaf_ip +"---------------------")
print("\n\n-------------------- Finished processing, leafs skipped-------------------: " )
for ls in leaf_skipped:
    print(ls)
