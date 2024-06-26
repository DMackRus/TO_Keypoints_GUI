import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import butter,filtfilt
import math
from dataclasses import dataclass
import yaml

@dataclass
class derivative_interpolator():
    keyPoint_method: str
    minN: int
    maxN: int
    acellThreshold: float
    jerkThreshold: float
    iterative_error_threshold: float
    vel_change_required: float

class interpolator():
    def __init__(self, task, trajecNumber):

        startPath = "savedTrajecInfo/" + task
        self.task = task
        self.trajecNumber = trajecNumber

        self.A_matrices = []
        self.B_matrices = []
        self.states = []
        self.controls = []
        
        # -------------------------------- Load meta data info -------------------------------------------
        with open(startPath + '/meta_data.yaml', 'r') as file:
            task_config = yaml.safe_load(file)

        self.robots = task_config['robots']
        self.bodies = []
        try:
            self.bodies = task_config['bodies']
        except:
            pass

        self.dof_pos = 0
        self.dof_vel = 0
        self.num_ctrl = 0
        for robot in task_config['robots']:
            try:
                if(task_config['robots'][robot]['base'] == True):
                    self.dof_pos += 7
                    self.dof_vel += 6
                    self.quat_w_indices.append(self.dof_pos - 4)
            except:
                pass

            self.dof_pos += task_config['robots'][robot]['num_joints']
            self.dof_vel += task_config['robots'][robot]['num_joints']
            self.num_ctrl += task_config['robots'][robot]['num_actuators']

        self.quat_w_indices = []

        if(len(self.bodies)):
            for body in task_config['bodies']:
                self.dof_pos += task_config['bodies'][body]['positions']
                self.dof_vel += (task_config['bodies'][body]['positions'])

                # TODO - this is quite hard coded atm and untested for multiple bodies with different orientations
                try:
                    if(task_config['bodies'][body]['orientation_no_w'] == 3):
                        self.dof_vel += 3
                        self.dof_pos += 3
                except:
                    if( task_config['bodies'][body]['orientations'] == 4):
                        self.dof_vel += 3
                        self.dof_pos += task_config['bodies'][body]['orientations']
                        self.quat_w_indices.append(self.dof_pos - 1)

        # print(f'dof pos: {self.dof_pos}, dof vel: {self.dof_vel}, num ctrl: {self.num_ctrl}')
        # print(f'quat w indices: {self.quat_w_indices}')

        # -------------------------------------------------------------------------------------------------
        
        pandas = pd.read_csv(startPath + "/" + str(self.trajecNumber) + '/A_matrices.csv', header=None)
        pandas = pandas[pandas.columns[:-1]]
        rows, cols = pandas.shape
        self.trajecLength = rows 

        tempPandas = pandas.iloc[0:self.trajecLength]
        self.A_matrices_load = tempPandas.to_numpy()

        pandas = pd.read_csv(startPath + "/" + str(self.trajecNumber) + '/B_matrices.csv', header=None)
        pandas = pandas[pandas.columns[:-1]]
        rows, cols = pandas.shape

        tempPandas = pandas.iloc[0:self.trajecLength]
        self.B_matrices_load = tempPandas.to_numpy()

        pandas = pd.read_csv(startPath + "/" + str(self.trajecNumber) + '/states.csv', header=None)
        pandas = pandas[pandas.columns[:-1]]
        rows, cols = pandas.shape

        self.num_states = self.dof_pos + self.dof_vel

        tempPandas = pandas.iloc[0:self.trajecLength]
        self.states = tempPandas.to_numpy()

        pandas = pd.read_csv(startPath + "/" + str(self.trajecNumber) +  '/controls.csv', header=None)
        pandas = pandas[pandas.columns[:-1]]
        rows, cols = pandas.shape
        self.num_ctrl = cols

        tempPandas = pandas.iloc[0:self.trajecLength]
        self.controls = tempPandas.to_numpy()

        self.A_matrices = np.zeros((self.trajecLength, self.num_states, self.num_states))
        self.B_matrices = np.zeros((self.trajecLength, self.num_states, self.num_ctrl))

        #reshape 2nd index into two indices
        # self.A_matrices = self.A_matrices_load.reshape((self.trajecLength, self.dof_vel, self.num_states))
        for i in range(self.trajecLength):
            for j in range(self.num_states):
                for k in range(self.num_states):
                    self.A_matrices[i][j][k] = self.A_matrices_load[i][j*self.num_states + k]

        # load the B_matrices values
        for i in range(self.trajecLength):
            for j in range(self.num_states):
                for k in range(self.num_ctrl):
                    self.B_matrices[i][j][k] = self.B_matrices_load[i][j*self.num_ctrl + k]
            

        if(0):
            T = 5.0         # Sample Period
            fs = 100.0      # sample rate, Hz
            cutoff = 1      # desired cutoff frequency of the filter, Hz ,      slightly higher than actual 1.2 Hz
            nyq = 0.5 * fs  # Nyquist Frequency
            order = 2       # sin wave can be approx represented as quadratic
            n = int(T * fs) # total number of samples

            self.filteredTrajectory = self.A_matrices[0].copy()

            for i in range(len(self.A_matrices[0])):
                
                # self.filteredTrajectory[:,i] = self.butter_lowpass_filter(self.A_matrices[0][:,i].copy(), cutoff, nyq, order)

                # self.A_matrices[0][:,i] = self.filteredTrajectory[:,i].copy()
                self.filteredTrajectory[:,i] = filterArray(self.A_matrices[0][:,i].copy())
                self.A_matrices[0][:,i] = self.filteredTrajectory[:,i].copy()

        else:
            self.filteredTrajectory = self.A_matrices.copy()

        self.dynParams = []

    def InterpolateTrajectory(self, trajecNumber, dynParams):

        self.dynParams = dynParams
        keyPoints_vel = self.generateKeypoints(self.A_matrices, self.B_matrices, self.states.copy(), self.controls.copy(), self.dynParams.copy())

        # If there are quaternions, generate key points for them
        key_points_w = []
        if(len(self.quat_w_indices)):
            key_points_w = np.arange(0, self.trajecLength, 5)

            if(key_points_w[-1] != self.trajecLength - 1):
                key_points_w = np.append(key_points_w, self.trajecLength - 1)

        A_all_interpolations = []
        B_all_interpolations = []
        for i in range(len(self.dynParams)):
            A_interpolation, B_interpolation = self.generateLinInterpolation(self.A_matrices, self.B_matrices, keyPoints_vel[i].copy(), key_points_w.copy())
            A_all_interpolations.append(A_interpolation)
            B_all_interpolations.append(B_interpolation)

        interpolatedTrajectory_A = np.zeros((len(self.dynParams), self.trajecLength, self.num_states, self.num_states))
        interpolatedTrajectory_B = np.zeros((len(self.dynParams), self.trajecLength, self.num_states, self.num_ctrl))
        errors = np.zeros((len(self.dynParams)))

        for i in range(len(self.dynParams)):
            interpolatedTrajectory_A[i,:,:,:] = A_all_interpolations[i].copy()
            errors[i] = self.calcErrorOverTrajectory(self.A_matrices, A_all_interpolations[i])
            # print("error from A: ", errors[i])
            errors[i] += self.calcErrorOverTrajectory(self.B_matrices, B_all_interpolations[i])
            # print("error from B: ", errors[i])

        return self.filteredTrajectory, interpolatedTrajectory_A, self.A_matrices, errors, keyPoints_vel, key_points_w
    
    def calcErrorOverTrajectory(self, groundTruth, prediction):
        '''
        Calculate a single number for the error over a trajectory between the true
        trajectory and our interpolation

        '''
        sum_abs_diff = np.zeros((groundTruth.shape[1], groundTruth.shape[2]))
        for t in range(self.trajecLength):
            sum_abs_diff += abs((groundTruth[t] - prediction[t]))

        #Average over the trajectory
        sum_abs_diff /= self.trajecLength

        # Aevrage over the size of the matrix
        MAE = np.sum(sum_abs_diff) / (groundTruth.shape[1] * groundTruth.shape[2])

        return MAE 
    
    def returnTrajecInformation(self):
        self.jerkProfile = self.calcJerkOverTrajectory(self.states)
        self.accelProfile = self.calculateAccellerationOverTrajectory(self.states)

        return self.jerkProfile, self.accelProfile, self.states.copy(), self.controls.copy()

    def calculateAccellerationOverTrajectory(self, trajectoryStates):
        # state vector = self.dof_pos + self.dof_vel
        acell = np.zeros((self.trajecLength - 1, self.dof_vel))


        for i in range(self.trajecLength - 1):

            vel1 = trajectoryStates[i,self.dof_pos:].copy()
            vel2 = trajectoryStates[i+1,self.dof_pos:].copy()

            currentAccel = vel2 - vel1

            acell[i,:] = currentAccel

        return acell

    def calcJerkOverTrajectory(self, trajectoryStates):
        jerk = np.zeros((self.trajecLength - 2, self.dof_vel))

        for i in range(self.trajecLength - 2):

            state1 = trajectoryStates[i,self.dof_pos:].copy()
            state2 = trajectoryStates[i+1,self.dof_pos:].copy()
            state3 = trajectoryStates[i+2,self.dof_pos:].copy()

            accel1 = state3 - state2
            accel2 = state1 - state1

            currentJerk = accel2 - accel1

            jerk[i,:] = currentJerk

        return jerk
    
    def generateKeypoints(self, A_matrices, B_matrices, trajectoryStates, trajectoryControls, dynParameters):
        keyPoints = [None] * len(dynParameters)

        for i in range(len(dynParameters)):

            if(dynParameters[i].keyPoint_method =="setInterval"):
                keyPoints[i] = self.keyPoints_setInterval(dynParameters[i])
            elif(dynParameters[i].keyPoint_method =="adaptiveJerk"):
                keyPoints[i] = self.keyPoints_adaptiveJerk(trajectoryStates, dynParameters[i])
            elif(dynParameters[i].keyPoint_method =="adaptiveAccel"):
                keyPoints[i] = self.keyPoints_adaptiveAccel(trajectoryStates, dynParameters[i])
            elif(dynParameters[i].keyPoint_method =="iterativeError"):
                keyPoints[i] = self.keyPoints_iteratively(A_matrices, dynParameters[i])
            elif(dynParameters[i].keyPoint_method =="magVelChange"):
                keyPoints[i] = self.keyPoints_magVelChange(trajectoryStates, trajectoryControls, dynParameters[i])
            else: 
                print("keypoint method not found")

        return keyPoints
    
    def keyPoints_setInterval(self, dynParameters):
        keyPoints = [[] for x in range(self.dof_vel)]

        for i in range(self.dof_vel):
            keyPoints[i].append(0)

        minN = dynParameters.minN
    
        for i in range(self.dof_vel):
            counter = 0
            for j in range(self.trajecLength - 1):
                counter += 1
                if counter >= minN:
                    counter = 0
                    keyPoints[i].append(j)

        for i in range(self.dof_vel):
            keyPoints[i].append(self.trajecLength - 1)

        return keyPoints 
    
    def keyPoints_adaptive_velocity(self, trajectoryStates, dynParameters):
        mainKeyPoints = [[] for x in range(self.dof_vel)]
        keyPoints = [[] for x in range(self.dof_vel)]

        last_direction = [0] * self.dof_vel

        for i in range(self.dof_pos):
            mainKeyPoints[i].append(0)

        velProfile = self.states[0][:, self.dof_vel:2*self.dof_vel]

        direction_temp = []

        for j in range(1, len(velProfile)):
            direction_temp.append(velProfile[j, 2] - velProfile[j-1, 2])

        # plt.plot(velProfile[:, 2])
        # plt.plot(direction_temp)
        # plt.show()
        # velProfile = self.calculateAccellerationOverTrajectory(self.states[0])

        for i in range(self.dof_vel):
            for j in range(1, len(velProfile)):

                current_direction = velProfile[j, i] - velProfile[j-1, i]

                change_in_direction = current_direction * last_direction[i]

                if(change_in_direction <= 0):
                    mainKeyPoints[i].append(j - 1)
                else:
                    pass
                    # if(abs(current_direction - last_direction[i]) > 0.0002):
                    #     mainKeyPoints[i].append(j)
                    
                last_direction[i] = current_direction

        for i in range(self.dof_vel):
            for j in range(len(mainKeyPoints[i])):
                if(j == 0):
                    keyPoints[i].append(mainKeyPoints[i][j])
                else:
                    keyPoints[i].append(mainKeyPoints[i][j])

        for i in range(self.dof_vel):
            keyPoints[i].append(self.trajecLength - 1)
        
        return keyPoints 

    def keyPoints_magVelChange(self, trajectoryStates, trajectoryControls, dynParameters):
        minN = dynParameters.minN
        maxN = dynParameters.maxN
        # velChangeRequired = 2.0
        velChangeRequired = dynParameters.vel_change_required

        keyPoints = [[] for x in range(self.dof_vel)]
        # currentVelChange = np.zeros((self.dof_pos))
        lastVelCounter = np.zeros((self.dof_vel))
        lastVelDirection = np.zeros((self.dof_vel))

        counter = np.zeros((self.dof_vel))

        for i in range(self.dof_vel):
            keyPoints[i].append(0)
            lastVelCounter[i] = trajectoryStates[0, i + self.dof_vel]

        for i in range(self.dof_vel):
            for j in range(1, self.trajecLength):
                counter[i] += 1

                # velChange = trajectoryStates[j+1, i + self.dof_vel] - trajectoryStates[j, i + self.dof_vel]
                # currentVelChange[i] += velChange
                currentVelDirection = trajectoryStates[j, i + self.dof_vel] - trajectoryStates[j-1, i + self.dof_vel]
                currentVelChange = trajectoryStates[j, i + self.dof_vel] - lastVelCounter[i]

                if(currentVelChange > velChangeRequired or currentVelChange < -velChangeRequired):
                    keyPoints[i].append(j)
                    lastVelCounter[i] = trajectoryStates[j, i + self.dof_vel]
                else:
                    if(counter[i] >= maxN):
                        keyPoints[i].append(j)
                        counter[i] = 0
                        lastVelCounter[i] = trajectoryStates[j, i + self.dof_vel]
                    else:
                        if(currentVelDirection * lastVelDirection[i] < 0):
                            if(counter[i] >= minN):
                                keyPoints[i].append(j)
                                lastVelCounter[i] = trajectoryStates[j, i + self.dof_vel]
                                counter[i] = 0

                lastVelDirection[i] = currentVelDirection

        for i in range(self.dof_vel):
            if(keyPoints[i][-1] != self.trajecLength - 1):
                keyPoints[i].append(self.trajecLength - 1)

        return keyPoints

    def keyPoints_adaptiveJerk(self, trajectoryStates, dynParameters):
        mainKeyPoints = [[] for x in range(self.dof_vel)]
        keyPoints = [[] for x in range(self.dof_vel)]

        for i in range(self.dof_vel):
            mainKeyPoints[i].append(0)

        counterSinceLastEval = np.zeros((self.dof_vel))
        outsideHysterisis = [False] * self.dof_vel
        resetToZeroAddKeypoint = [False] * self.dof_vel

        minN = dynParameters.minN
        maxN = dynParameters.maxN
        jerkThreshold = dynParameters.jerkThreshold
        # temp
        # velGradCubeSensitivity = 0.0002

        jerkProfile = self.calcJerkOverTrajectory(self.states)

        for i in range(self.dof_vel):
            for j in range(1, len(jerkProfile)):

                # if(outsideHysterisis[i] == True):
                #     if(jerkProfile[j, i] < jerkSensitivity and jerkProfile[j, i] > -jerkSensitivity):
                #         mainKeyPoints[i].append(j)
                #         outsideHysterisis[i] = False
                #         resetToZeroAddKeypoint[i] = True
                #         counterSinceLastEval[i] = 0
                #     else:
                #         pass
                #         # counterSinceLastEval[i] += 1
                #         # if(counterSinceLastEval[i] >= minN):
                #         #     mainKeyPoints[i].append(j)
                #         #     counterSinceLastEval[i] = 0

                # else:
                #     if(jerkProfile[j, i] > jerkSensitivity or jerkProfile[j, i] < -jerkSensitivity):
                #         # keyPoints[i].append(j-5)
                #         if(mainKeyPoints[i][-1] != j-1):
                #             mainKeyPoints[i].append(j-1)
                #         mainKeyPoints[i].append(j)
                #         outsideHysterisis[i] = True
                #         resetToZeroAddKeypoint[i] = False
                #         counterSinceLastEval[i] = 0

                #     if(resetToZeroAddKeypoint[i] == True):
                #         # print("reset to zero add keypoint")
                #         if(jerkProfile[j, i] < 0.000001 and jerkProfile[j, i] > -0.000001):
                #             mainKeyPoints[i].append(j)
                #             resetToZeroAddKeypoint[i] = False
                #             counterSinceLastEval[i] = 0

                #     if(counterSinceLastEval[i] >= maxN):
                #         mainKeyPoints[i].append(j)
                #         counterSinceLastEval[i] = 0

                #     counterSinceLastEval[i] = counterSinceLastEval[i] + 1

                if(counterSinceLastEval[i] >= minN):
                    # print("jerk profile: " + str(jerkProfile[j, i]))
                    if(jerkProfile[j, i] > jerkThreshold or jerkProfile[j, i] < -jerkThreshold):
                        mainKeyPoints[i].append(j)
                        counterSinceLastEval[i] = 0
                
                if(counterSinceLastEval[i] >= maxN):
                    mainKeyPoints[i].append(j)
                    counterSinceLastEval[i] = 0

                counterSinceLastEval[i] = counterSinceLastEval[i] + 1

        for i in range(self.dof_vel):
            for j in range(len(mainKeyPoints[i])):
                if(j == 0):
                    keyPoints[i].append(mainKeyPoints[i][j])
                else:
                    # keyPoints[i].append(mainKeyPoints[i][j] - 15)
                    # keyPoints[i].append(mainKeyPoints[i][j] - 10)
                    # keyPoints[i].append(mainKeyPoints[i][j] - 5)
                    keyPoints[i].append(mainKeyPoints[i][j])
                    # keyPoints[i].append(mainKeyPoints[i][j] + 5)
                    # keyPoints[i].append(mainKeyPoints[i][j] + 10)
                    # keyPoints[i].append(mainKeyPoints[i][j] + 15)

        for i in range(self.dof_vel):
            keyPoints[i].append(self.trajecLength - 1)
        
        return keyPoints 

    def keyPoints_adaptiveAccel(self, trajectoryStates, dynParameters):
        keyPoints = [[] for x in range(self.dof_vel)]

        for i in range(self.dof_vel):
            keyPoints[i].append(0)

        counterSinceLastEval = np.zeros((self.dof_vel))

        minN = dynParameters.minN
        maxN = dynParameters.maxN
        acellThreshold = dynParameters.acellThreshold

        accelProfile = self.calculateAccellerationOverTrajectory(self.states)

        for i in range(self.dof_vel):
            for j in range(len(accelProfile)):

                if(counterSinceLastEval[i] >= minN):
                    if(accelProfile[j, i] > acellThreshold or accelProfile[j, i] < -acellThreshold):
                        keyPoints[i].append(j)
                        counterSinceLastEval[i] = 0
                
                if(counterSinceLastEval[i] >= maxN):
                    keyPoints[i].append(j)
                    counterSinceLastEval[i] = 0

                counterSinceLastEval[i] = counterSinceLastEval[i] + 1

        for i in range(self.dof_vel):
            keyPoints[i].append(self.trajecLength - 1)
        
        return keyPoints 

    def keyPoints_iteratively(self, trajectoryStates, dynParameters):
        keyPoints = [[] for x in range(self.dof_vel)]
        for i in range(self.dof_vel):
            keyPoints[i].append(0)

        minN = dynParameters.minN
        iter_error_thresh = dynParameters.iterative_error_threshold

        startIndex = 0
        endIndex = self.trajecLength - 1

        for i in range(self.dof_vel):
            binComplete = False
            listofIndicesCheck = []
            indexTuple = (startIndex, endIndex)
            listofIndicesCheck.append(indexTuple)
            subListIndices = []
            subListWithMidpoints = []

            while(not binComplete):

                allChecksComplete = True
                for j in range(len(listofIndicesCheck)):

                    approximationGood, midIndex = self.oneCheck(trajectoryStates, listofIndicesCheck[j], i, minN, iter_error_thresh)

                    if not approximationGood:
                        allChecksComplete = False
                        
                        indexTuple1 = (listofIndicesCheck[j][0], midIndex)
                        indexTuple2 = (midIndex, listofIndicesCheck[j][1])
                        subListIndices.append(indexTuple1)
                        subListIndices.append(indexTuple2)
                    else:
                        subListWithMidpoints.append(listofIndicesCheck[j][0])
                        subListWithMidpoints.append(midIndex)
                        subListWithMidpoints.append(listofIndicesCheck[j][1])

                if(allChecksComplete):
                    binComplete = True
                    for k in range(len(subListWithMidpoints)):
                        keyPoints[i].append(subListWithMidpoints[k])

                    subListWithMidpoints = []

                listofIndicesCheck = subListIndices.copy()
                subListIndices = []

        for i in range(self.dof_vel):
            keyPoints[i].sort()
            keyPoints[i] = list(dict.fromkeys(keyPoints[i]))

        return keyPoints
        
    def oneCheck(self, A_matrices, indexTuple, dofNum, minN, iter_error_thresh):
        approximationGood = False

        startIndex = indexTuple[0]
        endIndex = indexTuple[1]

        midIndex = int((startIndex + endIndex) / 2)
        startVals = A_matrices[startIndex,:]
        endVals = A_matrices[endIndex,:]

        if((endIndex - startIndex) <= minN):
            return True, midIndex

        trueMidVals = A_matrices[midIndex,:]
        diff = endVals - startVals
        linInterpMidVals = startVals + (diff/2)

        meanSqDiff = self.meansqDiffBetweenAMatrices(trueMidVals, linInterpMidVals, dofNum)
        # print("meanSqDiff: " + str(meanSqDiff))

        # 0.05 for reaching and pushing
        #~0.001 for pendulum

        if(meanSqDiff < iter_error_thresh):
            approximationGood = True

        return approximationGood, midIndex

    def meanSqDiffMatrices(self, matrix1, matrix2):
        meanSqDiff = 0
        sumsqDiff = 0
        counter = 0

        for i in range(len(matrix1)):
            sqDiff = abs(matrix1[i] - matrix2[i])
            
            if sqDiff > 10:
                # print("large error: " + str(sqDiff) + " at index: " + str(i) + " with values: " + str(matrix1[i]) + " and " + str(matrix2[i]))
                pass
                
            else:
                counter = counter + 1
                sumsqDiff = sumsqDiff + sqDiff
                

        meanSqDiff = sumsqDiff / counter

        return meanSqDiff

    
    def sumsqDiffBetweenAMatrices(self, matrix1, matrix2):
        sumsqDiff = 0

        for i in range(len(matrix1)):
            sqDiff = (matrix1[i] - matrix2[i])**2

            sumsqDiff = sumsqDiff + sqDiff

        return sumsqDiff

    def meansqDiffBetweenAMatrices(self, matrix1, matrix2, dofNum):
        sum_sq_diff = 0
        counter = 0
        counterSmallVals = 0
        offsets = [0, self.dof_pos]

        for i in range(2):
            column_index = offsets[i] + dofNum
            sq_diff_column = (matrix1[:,column_index] - matrix2[:,column_index]) ** 2
            sum_sq_diff += sq_diff_column.sum()

        mean_sq_diff = (sum_sq_diff / (2 * self.dof_vel))
        
        return mean_sq_diff
    
    def generateLinInterpolation(self, A_matrices, B_matrices, reEvaluationIndicies, key_points_w):
        A_linInterpolationData = np.zeros((self.trajecLength, self.num_states, self.num_states))
        B_linInterpolationData = np.zeros((self.trajecLength, self.num_states, self.num_ctrl))

        for i in range(self.dof_vel):
            for j in range(len(reEvaluationIndicies[i]) - 1):
                    
                start_index = reEvaluationIndicies[i][j]
                end_index = reEvaluationIndicies[i][j + 1]

                # take the column values at start and end index
                startVals_pos = A_matrices[start_index, :, i]
                startVals_vel = A_matrices[start_index, :, i + self.dof_pos]

                if(i < self.num_ctrl):
                    startVals_B = B_matrices[start_index, :, i]

                endVals_pos = A_matrices[end_index, :, i]
                endVals_vel = A_matrices[end_index, :, i + self.dof_pos]

                if(i < self.num_ctrl):
                    endVals_B = B_matrices[end_index, :, i]

                interval = end_index - start_index
                diff_pos = endVals_pos - startVals_pos
                diff_vel = endVals_vel - startVals_vel
                if(i < self.num_ctrl):
                    diff_B = endVals_B - startVals_B

                for k in range(interval):
                    A_linInterpolationData[start_index + k, :, i] = startVals_pos + (diff_pos * (k / interval))
                    A_linInterpolationData[start_index + k, :, i + self.dof_pos] = startVals_vel + (diff_vel * (k / interval))

                    if(i < self.num_ctrl):
                        B_linInterpolationData[start_index + k, :, i] = startVals_B + (diff_B * (k / interval))

        # Handle any quaternions w interpolation
        for i in range(len(self.quat_w_indices)):
            for j in range(len(key_points_w) - 1):
                start_index = key_points_w[j]
                end_index = key_points_w[j + 1]

                startVals = A_matrices[start_index, :, self.quat_w_indices[i]]
                endVals = A_matrices[end_index, :, self.quat_w_indices[i]]

                diff = endVals - startVals
                interval = end_index - start_index

                A_linInterpolationData[start_index, :, self.quat_w_indices[i]] = startVals

                for k in range(1, interval):
                    A_linInterpolationData[start_index + k, :, self.quat_w_indices[i]] = startVals + (diff * (k / interval))

        A_linInterpolationData[len(A_linInterpolationData) - 1,:] = A_linInterpolationData[len(A_linInterpolationData) - 2,:]

        return A_linInterpolationData, B_linInterpolationData
    
    def butter_lowpass_filter(self, data, cutoff, nyq, order):
        normal_cutoff = cutoff / nyq
        # Get the filter coefficients 
        b, a = butter(order, normal_cutoff, btype='low', analog=False)
        y = filtfilt(b, a, data)
        return y

def testFilter():
    pass

def filterArray(unfiltered):
    yn1 = unfiltered[0]
    xn1 = unfiltered[0]

    filtered = []

    for i in range(len(unfiltered)):

        xn = unfiltered[i]
        yn = 0.2283*yn1 + 0.3859*xn + 0.3859*xn1

        xn1 = xn
        yn1 = yn

        filtered.append(yn)

    # plt.plot(filtered)
    # plt.plot(unfiltered)
    # plt.show()
    return filtered

def ICRATemp():
    myInterp = interpolator(1, 1)

    dynParams = [5, 200, 0.0005]

    trueTrajec, interpolatedTrajec, unfilteredTrajec, errors, reEvaluationIndices, iterativeKeyPoints = myInterp.InterpolateTrajectory(0, dynParams)
            
    index = 13

    highlightedIndices = np.copy(unfilteredTrajec[reEvaluationIndices, ])
    highlightedIndicesIterative = np.copy(unfilteredTrajec[iterativeKeyPoints, ])
    numEvals = len(reEvaluationIndices)

    yellow = '#EEF30D'
    black = '#000000'
    darkBlue = '#103755'

    plt.figure(figsize=(5,3))
    plt.plot(trueTrajec[:,index], color = darkBlue, label='Ground truth', linewidth=3)
    # plt.plot(interpolatedTrajec[0,:,index], color = yellow, label='interpolated')
    # plt.scatter(reEvaluationIndices, highlightedIndices[:, index], s=10, color = yellow, zorder=10)
    plt.plot(interpolatedTrajec[1,:,index], color = yellow, label='interpolated', linewidth=1, alpha = 1)
    plt.scatter(iterativeKeyPoints, highlightedIndicesIterative[:, index], s=10, color = yellow, alpha = 1, zorder=10)
    # plt.legend()
    # turn off y axis
    plt.gca().axes.get_yaxis().set_visible(False)
    # save as svg
    plt.savefig('test.svg', format='svg', dpi=1200)
    plt.show()

    index += 1

def test():
    myinterp = interpolator("panda_pushing_heavy_clutter", 1)

    interpolationTypes = ["setInterval", "adaptiveAccel", "adaptiveJerk", "iterativeError", "magVelChange"]
    method = interpolationTypes[3]
    minN = 5
    maxN = 100
    dynParams = [derivative_interpolator(method, minN, maxN, 0.005, 0.005, 0.0005, 0)]
    trueTrajec, interpolatedTrajec, unfilteredTrajec, errors, keyPoints, key_points_w = myinterp.InterpolateTrajectory(0, dynParams)


    row = 5
    col = 25

    dof_pos = 23
    dof_vel = 23

    index = (row * (dof_pos + dof_vel)) + col

    
    keyPoints_col = 0

    # get the column
    # check it against size of dof vel
    #TODO - fix this for multiple quaternions
    if(len(key_points_w) and col == dof_pos - 1):
        displayKeypoints = key_points_w
        highlightedIndices = np.copy(unfilteredTrajec[displayKeypoints, row, col])
    else:
        displayKeypoints = keyPoints[0]
        # 0 -> dof_pos - 1, dof_pos -> dof_pos + dof_vel - 1
        if(col >= dof_pos):
            keyPoints_col = col - dof_pos
        else:
            keyPoints_col = col
        # displayKeypoints = displayKeypoints[col % self.dof_vel]
        displayKeypoints = displayKeypoints[keyPoints_col]
        highlightedIndices = np.copy(unfilteredTrajec[displayKeypoints, row, col])

    numEvals = len(displayKeypoints)

    black = '#000000'
    # red = '#f70f0f'

    dark_blue = '#1E90FF'
    red = '#fa2020'


    plt.figure(figsize=(10, 3))
    plt.plot(trueTrajec[:, row, col], color = black, label='Ground truth')
    plt.scatter(displayKeypoints, highlightedIndices, s=20, color = red, zorder=10)
    plt.plot(interpolatedTrajec[0, :, row, col], color = red, label = 'Interpolated')
    plt.show()

        # self.plot_AB.clear()

        # if(self.showFilter):
        #     print("showing filtered trajectory")
        #     self.plot_AB.plot(self.trueTrajec[:, row, col], color = 'orange', label='Ground truth')

        # self.plot_AB.plot(self.unfilteredTrajec[:, row, col], color = self.black, label='Unfiltered')

        # # Plot keypoints
        # self.plot_AB.scatter(displayKeypoints, highlightedIndices, s=10, color = self.yellow, zorder=10)

        # self.plot_AB.plot(self.interpolatedTrajec[self.interpTypeNum, :, row, col], color = self.yellow, label = 'Interpolated')
        # self.plot_AB.legend(loc='upper right')
        # self.plot_AB.set_title('A matrix val over trajectory', fontsize=15, color= self.white, fontweight='bold')

        # # set y lims
        # minVal = np.min(self.unfilteredTrajec[:,row, col])
        # maxVal = np.max(self.unfilteredTrajec[:,row, col])

        # if (maxVal - minVal < 0.1):
        #     self.plot_AB.set_ylim([minVal - 0.05, maxVal + 0.05])
        

        # evalsString = "Evals: " + str(self.numEvals)

        # # Anchor text above plot - offset from plot by 10%
        # at = AnchoredText(evalsString, loc='upper left', prop=dict(size=8), frameon=True, bbox_to_anchor=(0.9, 1.1), bbox_transform=self.plot_AB.transAxes)
        
        # at.patch.set_boxstyle("round,pad=0.,rounding_size=0.2")
        # self.plot_AB.add_artist(at)


        # at2 = AnchoredText("Error: " + str(round(self.errors[self.interpTypeNum], 2)) + "",
        #                loc='lower left', prop=dict(size=8), frameon=True,
        #                bbox_to_anchor=(0., 1.05),
        #                bbox_transform=self.plot_AB.transAxes
        #                )
        # at2.patch.set_boxstyle("round,pad=0.,rounding_size=0.2")
        # self.plot_AB.add_artist(at2)
        # self.canvas_AB.draw()




if __name__ == "__main__":
    test()

    # Generate a sine curve with 100 points
    x = np.linspace(0, 1, 100)
    y = np.sin(2*np.pi*x)


    key_points_good =[0, 12, 25, 37, 50, 63, 75, 87, 99]
    key_points_bad = [0, 25, 50, 75, 99]

    # Generate a linear intepolation between those key_points on the sine curve
    interp1 = []
    interp2 = []

    for i in range(len(key_points_bad) - 1):
        temp = np.linspace(y[key_points_bad[i]], y[key_points_bad[i+1]], key_points_bad[i+1] - key_points_bad[i] + 1)
        for j in range(len(temp) - 1):
            interp1.append(temp[j])

    for i in range(len(key_points_good) - 1):
        temp = np.linspace(y[key_points_good[i]], y[key_points_good[i+1]], key_points_good[i+1] - key_points_good[i] + 1)
        for j in range(len(temp) - 1):
            interp2.append(temp[j])


    # Do some error calculation methods between these two
    MAE = 0
    MSE = 0
    RMSE = 0

    # MSE
    for i in range(len(interp2)):
        MSE += (y[i] - interp2[i])**2
    MSE = MSE/len(interp2)

    # RMSE
    RMSE = np.sqrt(MSE)

    # MAE
    for i in range(len(interp2)):
        MAE += abs(y[i] - interp2[i])
    MAE = MAE/len(interp2)

    print(f' good approximation: MAE: {MAE}, MSE: {MSE}, RMSE: {RMSE}')

        # MSE
    for i in range(len(interp1)):
        MSE += (y[i] - interp1[i])**2
    MSE = MSE/len(interp1)

    # RMSE
    RMSE = np.sqrt(MSE)

    # MAE
    for i in range(len(interp1)):
        MAE += abs(y[i] - interp1[i])
    MAE = MAE/len(interp1)

    print(f' bad approximation: MAE: {MAE}, MSE: {MSE}, RMSE: {RMSE}')


    plt.plot(interp2, label = "good approximation")
    plt.plot(interp1, label = "bad approximation")
    plt.plot(y, label = "true value")
    plt.legend()
    plt.show()


