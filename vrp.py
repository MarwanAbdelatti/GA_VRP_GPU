import sys
import random
import math
import numpy as np
import matplotlib.pyplot as plt
import cProfile
from tqdm import tqdm

# from numba import float32, int64
# from numba import vectorize, guvectorize, jit, cuda

from timeit import default_timer as timer

pr = cProfile.Profile()
pr.enable

class node():
    def __init__(self, label, demand, posX, posY):
        self.label = label
        self.demand = demand
        self.X = posX
        self.Y = posY

class vrp():
    def __init__(self, capacity=None):
        self.capacity = capacity
        self.nodes = np.zeros((1,4), dtype=np.float32)

    def addNode(self, label, demand, posX, posY):
        newrow = np.array([label, demand, posX, posY], dtype=np.float32)
        self.nodes = np.vstack((self.nodes, newrow))

pop = []

def readInput():
	# Create VRP object:
    vrpManager = vrp()
    # vrpManager.addNode(0, 0, 82, 76) # Depot coordinate assignments

	## First reading the VRP from the input ##
    print('Reading data file...', end=' ')
    fo = open(sys.argv[3],"r")
    lines = fo.readlines()
    for i, line in enumerate(lines):
        while line.upper().startswith('CAPACITY'):
            inputs = line.split()
            vrpManager.capacity = np.float32(inputs[2])
			# Validating positive non-zero capacity
            if vrpManager.capacity <= 0:
                print(sys.stderr, 'Invalid input: capacity must be neither negative nor zero!')
                exit(1)
            break       
        while line.upper().startswith('NODE_COORD_SECTION'):
            i += 1
            line = lines[i]
            while not (line.upper().startswith('DEMAND_SECTION') or line=='\n'):
                inputs = line.split()
                vrpManager.addNode(np.int16(inputs[0]), 0.0, np.float32(inputs[1]), np.float32((inputs[2])))
                # print(vrpManager.nodes)
                i += 1
                line = lines[i]
                while (line=='\n'):
                    i += 1
                    line = lines[i]
                    if line.upper().startswith('DEMAND_SECTION'): break 
                if line.upper().startswith('DEMAND_SECTION'):
                    i += 1
                    line = lines[i] 
                    while not (line.upper().startswith('DEPOT_SECTION')):                  
                        inputs = line.split()
						# Validating demand not greater than capacity
                        if float(inputs[1]) > vrpManager.capacity:
                            print(sys.stderr,
							'Invalid input: the demand of the node %s is greater than the vehicle capacity!' % vrpManager.nodes[0])
                            exit(1)
                        if float(inputs[1]) < 0:
                            print(sys.stderr,
                            'Invalid input: the demand of the node %s cannot be negative!' % vrpManager.nodes[0])
                            exit(1)                            
                        vrpManager.nodes[int(inputs[0])][1] =  float(inputs[1])
                        i += 1
                        line = lines[i]
                        while (line=='\n'):
                            i += 1
                            line = lines[i]
                            if line.upper().startswith('DEPOT_SECTION'): break
                        if line.upper().startswith('DEPOT_SECTION'):
                            vrpManager.nodes = np.delete(vrpManager.nodes, 0, 0)
                            print('Done.')
                            return(vrpManager.capacity, vrpManager.nodes)

# @guvectorize([(float32[:], float32[:], float32[:], float32[:], float32[:], float32[:], float32[:,:], float32[:])], '(m),(m),(m),(m),(m),(n),(o,p)->()', target='cuda')
def distance(first_node, prev, next_node, last_node, individual, vrp_data):
	total_dist = 0
	# The first distance is from depot to the first node of the first route
	if individual[0] != 1:
		for k in range(len(vrp_data)):
			if vrp_data[k][0] == individual[0]:
				first_node = vrp_data[k]
				break
	else:
		first_node = vrp_data[0]

	x1 = vrp_data[0][2]
	x2 = first_node[2]
	y1 = vrp_data[0][3]
	y2 = first_node[3]

	dx = x1 - x2
	dy = y1 - y2
	total_dist = (round(math.sqrt(dx * dx + dy * dy)))
		
	# Then calculating the distances between the nodes
	for i in range(len(individual) - 2):
		if individual[i] != 1:
			for k in range(len(vrp_data)):
				if vrp_data[k][0] == individual[i]:
					prev = vrp_data[k]
					break
		else:
			prev = vrp_data[0]

		if individual[i+1] != 1:
			for k in range(len(vrp_data)):
				if vrp_data[k][0] == individual[i+1]:
					next_node = vrp_data[k]
					break
		else:
			next_node = vrp_data[0]

		x1 = prev[2]
		x2 = next_node[2]
		y1 = prev[3]
		y2 = next_node[3]

		dx = x1 - x2
		dy = y1 - y2
		total_dist += (round(math.sqrt(dx * dx + dy * dy)))

	# The last distance is from the last node of the last route to the depot

	last_node = next_node

	x1 = last_node[2]
	x2 = vrp_data[0][2]
	y1 = last_node[3]
	y2 = vrp_data[0][3]
	dx = x1 - x2
	dy = y1 - y2
	total_dist += (round(math.sqrt(dx * dx + dy * dy)))
	return(total_dist)

# @guvectorize([(float32[:,:], float32[:], float32[:])], '(m,n),(p)->()')
def fitness(vrp_data, individual):
    first_node = np.zeros(4, dtype=np.float32)
    prev = np.zeros(4, dtype=np.float32)
    next_node = np.zeros(4, dtype=np.float32)
    last_node = np.zeros(4, dtype=np.float32)

    totaldist = distance(first_node, prev, next_node, last_node, individual, vrp_data)
    no_of_vehicles = list(individual).count(1)

    return(totaldist)

#@jit(parallel=True)
def adjust(individual, vrp_data, vrp_capacity):
    # Delete duplicate nodes
    individual = individual.tolist()
    individual = sorted(set(individual), key=individual.index)

    # Check the missing nodes and insert them randomly
    missing_nodes = set(vrp_data[:,0]) - set(individual)

    for node in missing_nodes:
        individual.insert(random.randint(0, len(individual)-2), node)
    # Delete ones
    individual.remove(1)

    # repeated = True
    # while repeated:
    #     repeated = False
    #     for i1 in range(len(individual) - 1):
    #         for i2 in range(i1):
    #             if individual[i1] == individual[i2]:
    #                 haveAll = True
    #                 for i3 in range(len(vrp_data)):
    #                     nodeId = vrp_data[i3][0]
    #                     if nodeId not in individual: # ensure that All nodes (with demand > 0) are covered in each single solution
    #                         individual[i1] = nodeId
    #                         haveAll = False
    #                         break
    #                 if haveAll:
    #                     mask = np.ones(len(individual), dtype=bool)
    #                     mask[i1] = False
    #                     individual = individual[mask]
    #                 repeated = True
    #             if repeated: break
    #         if repeated: break
    # Adjust capacity exceed
    i = 0               # index
    reqcap = 0.0        # required capacity

    while i < len(individual)-1: 
        reqcap += vrp_data[vrp_data[:,0] == individual[i]][0,1] if individual[i] != 1 else 0.0
        if reqcap > vrp_capacity: 
            individual = np.insert(individual, i, np.float32(1))
            reqcap = 0.0
        i += 1

    # Adjust two consecutive depots
    # i = len(individual) - 2
    # while i >= 0:
    #     if individual[i] == 0 and individual[i + 1] == 0:
    #         mask = np.ones(len(individual), dtype=bool)
    #         mask[i] = False
    #         individual = individual[mask]
    #     i -= 1
    return individual
    
# Generating random initial population
def initializePop(vrp_data, popsize, vrp_capacity):
    print('GA evolving, please wait until finished...')
    popArr = []
    nodes = []
    nodes += [float(node[0]) for node in vrp_data]
    for i in range(0, popsize):
        individual = nodes.copy()
        random.shuffle(individual)
        individual.append(9999.0) # Any number != 1
        individual = adjust(np.asarray(individual, dtype=np.float32), np.asarray(vrp_data, dtype=np.float32), vrp_capacity)
        fitness_val = fitness(np.asarray(vrp_data, dtype=np.float32), np.asarray(individual, dtype=np.float32))
        individual[len(individual)-1] = fitness_val
        popArr += [individual]
    return(popArr)

def evolvePop(pop, vrp_data, iterations, vrp_capacity):
    def get_item(elem):
        return elem[len(elem)-1]

    old_fitness = 0.0
    tolerance_val = 0.0 # indication of convergence
    # Running the genetic algorithm
    for i in tqdm(range(iterations)):
        nextPop = []
        elite_count = len(pop)//20      # top 5% of the parents will remain in the new generation
        sorted_pop = pop.copy()
        sorted_pop.sort(key=get_item)

        # print('Population# %s min:' %i, sorted_pop[0][len(sorted_pop[0])-1])

        nextPop = sorted_pop[:elite_count]
        current_fitness = sorted_pop[len(sorted_pop)-1][len(sorted_pop[len(sorted_pop)-1])-1]
        if abs(current_fitness - old_fitness) > tolerance_val:
            old_fitness = sorted_pop[0][len(sorted_pop[0])-1]
        # else:
        #     print('Convergence occurred at iteration #', i)
        #     #break

		# Each one of this iteration will generate two descendants individuals. 
		# Therefore, to guarantee same population size, this will iterate half population size times
        # Also, we need to create a mask for uniform crossover
        # mask = []
        #for i in range(len(max(pop,key= lambda indiv: len(indiv)))):
        #for i in range(len(max(pop,key= lambda indiv: len(indiv)))//2):
        # for i in range(len(max(pop,key= lambda indiv: len(indiv)))//3):
        #for i in range(len(max(pop,key= lambda indiv: len(indiv)))//4):
            # mask.append(random.randint(0, 1))

        for j in range(round(((len(pop))-elite_count) / 2)):
            # Selecting randomly 4 individuals to select 2 parents by a binary tournament
            parentIds = {0}
            while len(parentIds) < 4:
                parentIds |= {random.randint(0, len(pop) - 1)}

            parentIds = list(parentIds)
            # Selecting 2 parents with the binary tournament
            parent1 = list(pop[parentIds[0]] if pop[parentIds[0]][len(pop[parentIds[0]])-1] < pop[parentIds[1]][len(pop[parentIds[1]])-1] else pop[parentIds[1]])
            parent2 = list(pop[parentIds[2]] if pop[parentIds[2]][len(pop[parentIds[2]])-1] < pop[parentIds[3]][len(pop[parentIds[3]])-1] else pop[parentIds[3]])

            child1 = parent1.copy()
            child2 = parent2.copy()

            # Performing Two-Point crossover and generating two children
            # Selecting (n/5 - 1) random cutting points for crossover, with the same points (indexes) for both parents, based on the shortest parent

            cutIdx = [0] * ((min(len(parent1) - 2, len(parent2) - 2))//5 - 1)
            for k in range(0, len(cutIdx)):
                cutIdx[k] = random.randint(1, min(len(parent1) - 2, len(parent2) - 2))
                while cutIdx[k] in cutIdx[:k]:
                    cutIdx[k] = random.randint(1, min(len(parent1) - 2, len(parent2) - 2))
            cutIdx.sort()

            for k in range(0, len(cutIdx), 2):
                if len(cutIdx) %2 == 1 and k == len(cutIdx) - 1: # Odd number
                    child1[cutIdx[k]:] = child2[cutIdx[k]:]
                    child2[cutIdx[k]:] = child1[cutIdx[k]:]
                else:                       
                    child1[cutIdx[k]:cutIdx[k + 1]] = child2[cutIdx[k]:cutIdx[k + 1]]
                    child2[cutIdx[k]:cutIdx[k + 1]] = child1[cutIdx[k]:cutIdx[k + 1]]        
            # Performing Uniform Crossover
            # for i in range(min(len(parent1) - 1, len(parent2) - 1)//3):
            #   if mask[i] == 1:
            #    #child1[i], child2[i] = child2[i], child1[i]

            #     #child1[2*i], child2[2*i] = child2[2*i], child1[2*i]
            #     #child1[2*i+1], child2[2*i+1] = child2[2*i+1], child1[2*i+1]
                   
            #     child1[3*i], child2[3*i] = child2[3*i], child1[3*i]
            #     child1[3*i+1], child2[3*i+1] = child2[3*i+1], child1[3*i+1]
            #     child1[3*i+2], child2[3*i+2] = child2[3*i+2], child1[3*i+2]

                #child1[4*i], child2[4*i] = child2[4*i], child1[4*i]
                #child1[4*i+1], child2[4*i+1] = child2[4*i+1], child1[4*i+1]
                #child1[4*i+2], child2[4*i+2] = child2[4*i+2], child1[4*i+2]
                #child1[4*i+3], child2[4*i+3] = child2[4*i+3], child1[4*i+3]

            nextPop = nextPop + [child1, child2]
		# Doing mutation: swapping two positions in one of the individuals, with 1:15 probability
        if random.randint(1, 5) == 1:
            # Random swap mutation
            x = random.randint(0, len(nextPop) - 1)
            ptomutate = nextPop[x]
            i1 = random.randint(0, len(ptomutate) - 2)
            i2 = random.randint(0, len(ptomutate) - 2)
            while ptomutate[i1] == 0.0:
                i1 = random.randint(0, len(ptomutate) - 2)
            while ptomutate[i2] == 0.0:
                i2 = random.randint(0, len(ptomutate) - 2)
            ptomutate[i1], ptomutate[i2] = ptomutate[i2], ptomutate[i1]

		# Adjusting individuals
        for k in range(len(nextPop)):
            individual = nextPop[k]
            individual = adjust(np.asarray(individual, dtype=np.float32), np.asarray(vrp_data, dtype=np.float32), vrp_capacity)
            fitness_val = fitness(np.asarray(vrp_data, np.float32), np.asarray(individual, np.float32))
            individual[len(individual)-1] = fitness_val
            nextPop[k] = individual
		# Updating population generation
        random.shuffle(nextPop)
        pop = nextPop
        # print('Population# %s min:' %i, pop)
    return (pop)

# depot_node = np.array(([[0, 0, 40, 40]]), dtype=np.float32) # Depot coordinate assignments
vrp_capacity, vrp_data = readInput()
popsize = int(sys.argv[1])
iterations = int(sys.argv[2])

#vrp_capacity = 40 # Temporarily!!
#popsize = 10  # Temporarily!!
#iterations = 20  # Temporarily!!
import multiprocessing as MLP
from concurrent.futures import ThreadPoolExecutor

cpu_no = MLP.cpu_count()
pool = ThreadPoolExecutor(max_workers=cpu_no)

start = timer()
# pop = initializePop(vrp_data, popsize, vrp_capacity)
future_1 = pool.submit(initializePop, vrp_data, popsize, vrp_capacity)
pop = future_1.result()

future_2 = pool.submit(evolvePop, pop, vrp_data, iterations, vrp_capacity)
pop = future_2.result()

# Selecting the best individual, which is the final solution
better = []

def get_item(idx):
    return(idx[len(idx) - 1])
individual = min(pop, key=get_item)
better = [1] + list(individual[:-1]) if individual[0] != 1 else list(individual[:-1])
t = int(timer()-start)

# Printing & plotting solution
print ('Solution by GA:\n', [x - 1 for x in better])
print ('Cost:', individual[-1])
# print('Time Elaplsed:', t, 's')

# Plot solution:
plt.scatter(vrp_data[1:][:,2], vrp_data[1:][:,3], c='b')
plt.plot(vrp_data[0][2], vrp_data[0][3], c='r', marker='s')

line_1 = None
for loc, i in enumerate(better[:-1]):
    if i != 1:
        # Text annotations for data points:
        plt.annotate(('%d\n"%d"'%(i, vrp_data[vrp_data[:,0]==i][0][1])), (vrp_data[vrp_data[:,0]==i][0][2]+1,vrp_data[vrp_data[:,0]==i][0][3]))
    if loc != len(better)-2:
        # Plot routes
        plt.plot([vrp_data[vrp_data[:,0]==i][0][2], vrp_data[vrp_data[:,0]==better[loc+1]][0][2]],\
         [vrp_data[vrp_data[:,0]==i][0][3], vrp_data[vrp_data[:,0]==better[loc+1]][0][3]]\
             , c='k', linestyle='--', alpha=0.3)
    else:
        line_1, = plt.plot([vrp_data[vrp_data[:,0]==i][0][2], vrp_data[0][2]],\
         [vrp_data[vrp_data[:,0]==i][0][3], vrp_data[0][3]], label='GA only: %d'%individual[-1]\
             , c='k', linestyle='--', alpha=0.3)

plt.axis('equal')

# Solve routes as TSP:
import tsp_cplex as tsp
tsp.solve([x - 1 for x in better], vrp_data, line_1)