from ast import Continue
from pyaci import Node, options, filters
import argparse
from argparse import RawTextHelpFormatter
import getpass


desc="""
python find_n_purge.py -delete 

1. Use delete option to  delete stale entries.
---> python find_n_purge_pass.py -delete -user admin -leaf_ip 10.197.146.198

2. Use without delete option, to show the stale entries
---> python find_n_purge_pass.py -list -user admin -leaf_ip 10.197.146.198

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
    print("\n\n*********************Processing " + leaf_ip)

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
    EpPD = leaf.mit.compUni().GET(**options.subtreeClass('compEpPD'))
    
    PEp = leaf.mit.opflexpPEpReg().GET(**options.subtreeClass('opflexpPEp'))

    PEpDict = {}
    for P in PEp:
        lnodeDn = P.__dict__['_properties']['domain']
        pepName = P.__dict__['_properties']['name']
        domainDn = "/".join(lnodeDn.split("/")[:-1])
        if domainDn not in PEpDict:
            PEpDict[domainDn] = []
        PEpDict[domainDn].append(P)

    # print(PEpDict)

    for eppd in EpPD:
       # print(eppd.Dn)
       EpPDset.add(eppd.Dn)
    
    stale = 0
    deleted = 0
    for idep in IDEp:   
        domName = idep.__dict__['_properties']['domName']
        ctrlrName = idep.__dict__['_properties']['ctrlrName']
        vendor = idep.__dict__['_properties']['vendorId']
        
        epgPKey = idep.__dict__['_properties']['epgPKey']
        epgName = epgPKey.split('/')[3][4:]
        apName = epgPKey.split('/')[2][3:]
        tenantName = epgPKey.split('/')[1][3:]

        epgName = apName +  "|" + epgName

        domain = "comp/" + "prov-" + vendor + "/"
        domain = domain + "ctrlr-[" + domName + "]" + "-" + ctrlrName

        # print("--------------------checking IDEp: -------- " + idep.Dn)

        eppd = leaf.mit.compUni().compProv(vendor).compCtrlr(domName, ctrlrName).compEpPD(idep.__dict__['_properties']['epgPKey'])    
        if eppd.Dn not in EpPDset:
            stale = stale + 1
            print("\n--------------------stale found: " + idep.Dn)
            print(eppd.Dn)

            
            if args.delete_option:
                leaf.toggleTestApi(True, 'policyelem')
                demand =  leaf.mit.opflexpPolicyReg().GET(**options.subtreeClass('opflexpPolicyDemand') & options.filter(filters.Eq('opflexpPolicyDemand.name', epgName) & filters.Eq('opflexpPolicyDemand.tenantName', tenantName)))
                if len(demand) == 0 :
                    print("\n--------------------No demand Mo found for EPG: " +  epgName)
                    print(tenantName)
                    continue

                queryClassId = demand[0].__dict__['_properties']['queryClassId']
                type = demand[0].__dict__['_properties']['type']
                pepList = []
                if domain in PEpDict:
                    pepList = PEpDict[domain]
                
                for pep in pepList:
                    reg = leaf.mit.opflexpPolicyReg()
                    pepName = pep.__dict__['_properties']['name']
                    pepDomain = pep.__dict__['_properties']['domain']
                    reg.Xml = '''<opflexpPolicyReg> 
                                    <opflexpPolicyDemand name='{0}' tenantName='{1}' type='{2}' queryClassId='{3}'>
                                          <opflexpPolicyConsumer pepName='{4}'  pepDomain='{5}'  status="deleted"/>
                                     </opflexpPolicyDemand>
                                  </opflexpPolicyReg>'''.format(epgName, tenantName, type, queryClassId, pepName, pepDomain)
                    leaf.toggleTestApi(True, 'opflexp')
                    reg.POST()
                    
                deleted = deleted + 1
                print("\n--------------------deleted IDep: " + idep.Dn)
    if stale == 0:
        print("\n--------------------No stale null-mac IDEp found in " + leaf_ip)
    else:
        print("\n--------------------Total stale null-mac IDEp found in " +leaf_ip  + "  = " + str(stale))
    if args.delete_option:
        if deleted == 0:
            print("\n--------------------No stale null-mac IDEp deleted in " + leaf_ip)
        else:
            print("\n--------------------Total stale null-mac IDEp deleted in " +leaf_ip  + "  = " + str(deleted))

print("\n\n-------------------- Finished processing, leafs skipped" )
for ls in leaf_skipped:
    print(ls)
