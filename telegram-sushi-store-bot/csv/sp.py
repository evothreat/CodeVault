import csv

def split_csv(file):
    with open(file) as rf:
        r = csv.reader(rf, delimiter=';')
        for row in r:
            row = list(filter(bool, row))
            if len(row) == 1:
                with open(row[0]+'.csv', 'w') as wf:
                    w = csv.writer(wf, delimiter=';')
                    # fixes excel read bug
                    head = next(r)
                    head[0] = ' ' + head[0]
                    w.writerow(head)
                    # read until whitespace
                    for row in r:
                        if not any(row):
                            break
                        w.writerow(row)
                                        
split_csv('товары.csv')
