import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import butter,filtfilt
import math

numTrajectoriesTest = 1

class interpolator():
    def __init__(self, trajecNumber, task):

        startPath = "savedTrajecInfo/" + task + "/"
        dof = 7
        num_ctrl = 7

        self.dof = dof
        self.task = task
        self.num_ctrl = num_ctrl
        self.numStates = self.dof * 2
        self.sizeOfAMatrix = self.numStates * self.numStates
        self.trajecNumber = 0
        
        pandas = pd.read_csv(startPath + str(self.trajecNumber) + '/A_matrices.csv', header=None)
        pandas = pandas[pandas.columns[:-1]]
        rows, cols = pandas.shape
        self.trajecLength = rows 
        print("trajec length " + str(self.trajecLength))

        self.testTrajectories = []
        self.states = []
        self.controls = []

        for i in range(numTrajectoriesTest):
            self.testTrajectories.append([])
            tempPandas = pandas.iloc[i*self.trajecLength:(i + 1)*self.trajecLength]
            self.testTrajectories[i] = tempPandas.to_numpy()
        print(self.testTrajectories[0][0])
        pandas = pd.read_csv(startPath + str(self.trajecNumber) + '/states.csv', header=None)
        pandas = pandas[pandas.columns[:-1]]

        for i in range(numTrajectoriesTest):
            self.states.append([])
            tempPandas = pandas.iloc[i*self.trajecLength:(i + 1)*self.trajecLength]
            self.states[i] = tempPandas.to_numpy()
        print(self.states[0][0])
        pandas = pd.read_csv(startPath + str(self.trajecNumber) +  '/controls.csv', header=None)
        pandas = pandas[pandas.columns[:-1]]

        for i in range(numTrajectoriesTest):
            self.controls.append([])
            tempPandas = pandas.iloc[i*self.trajecLength:(i + 1)*self.trajecLength]
            self.controls[i] = tempPandas.to_numpy()

        print("DATA LOADED")

        if(task == 2):
            T = 5.0         # Sample Period
            fs = 100.0       # sample rate, Hz
            cutoff = 1      # desired cutoff frequency of the filter, Hz ,      slightly higher than actual 1.2 Hz
            nyq = 0.5 * fs  # Nyquist Frequency
            order = 2       # sin wave can be approx represented as quadratic
            n = int(T * fs) # total number of samples

            self.filteredTrajectory = self.testTrajectories[0].copy()

            for i in range(len(self.testTrajectories[0][0])):
                
                self.filteredTrajectory[:,i] = self.butter_lowpass_filter(self.testTrajectories[0][:,i].copy(), cutoff, nyq, order)

        else:
            self.filteredTrajectory = self.testTrajectories[0].copy()

        self.dynParams = []
        self.error_dynLin = []
        self.evals_dynLin = []
        self.time_dynLin = []
        self.displayData_raw = []
        self.displayData_inteprolated = []

    def interpolateTrajectory(self, trajecNumber, dynParams):
        rawTrajec = self.testTrajectories[trajecNumber]

        self.dynParams = dynParams
        keyPoints = self.generateKeypoints(rawTrajec, self.controls[0].copy(), self.dynParams.copy())

        # print("keypoints generated")
        # print(keyPoints)

        setIntervalTrajectory = self.generateLinInterpolation(rawTrajec, keyPoints[0].copy())
        adaptiveJerkTrajectory = self.generateLinInterpolation(rawTrajec, keyPoints[1].copy())
        adaptiveAccellTrajectory = self.generateLinInterpolation(rawTrajec, keyPoints[2].copy())
        iterativeErrorTrajectory = self.generateLinInterpolation(rawTrajec, keyPoints[3].copy())

        #store lininterp and quadratic interp into interpolateTrajectory
        interpolatedTrajectory = np.zeros((4, self.trajecLength, len(rawTrajec[0])))
        errors = np.zeros((4))
        interpolatedTrajectory[0,:,:] = setIntervalTrajectory.copy()
        interpolatedTrajectory[1,:,:] = adaptiveJerkTrajectory.copy()
        interpolatedTrajectory[2,:,:] = adaptiveAccellTrajectory.copy()
        interpolatedTrajectory[3,:,:] = iterativeErrorTrajectory.copy()
        
        if(self.task == 2):
            errors[0] = self.calcMeanSumSquaredDiffForTrajec(self.filteredTrajectory, setIntervalTrajectory)
            errors[1] = self.calcMeanSumSquaredDiffForTrajec(self.filteredTrajectory, adaptiveJerkTrajectory)
            errors[2] = self.calcMeanSumSquaredDiffForTrajec(self.filteredTrajectory, adaptiveAccellTrajectory)
            errors[3] = self.calcMeanSumSquaredDiffForTrajec(self.filteredTrajectory, iterativeErrorTrajectory)
        else:
            errors[0] = self.calcMeanSumSquaredDiffForTrajec(rawTrajec, setIntervalTrajectory)
            errors[1] = self.calcMeanSumSquaredDiffForTrajec(rawTrajec, adaptiveJerkTrajectory)
            errors[2] = self.calcMeanSumSquaredDiffForTrajec(rawTrajec, adaptiveAccellTrajectory)
            errors[3] = self.calcMeanSumSquaredDiffForTrajec(rawTrajec, iterativeErrorTrajectory)

        return self.filteredTrajectory, interpolatedTrajectory, rawTrajec, errors, keyPoints
    
    def calcMeanSumSquaredDiffForTrajec(self, groundTruth, prediction):

        array1Size = len(groundTruth)
        array2Size = len(prediction)
        lenofTrajec = array2Size
        
        if(array1Size < array2Size):
            lenofTrajec = array1Size
        
        meanSqDiff = np.zeros((lenofTrajec))

        for i in range(lenofTrajec):
            meanSqDiff[i] = self.sumsqDiffBetweenAMatrices(groundTruth[i], prediction[i])
            
            # for j in range(size):

                # diffVals = abs((groundTruth[i, j] - prediction[i, j]))
                # SqDiff[i, j] = diffVals

        # for j in range(size):
        #     # stddev = np.std(SqDiff[:,j])
        #     # mean = np.mean(SqDiff[:,j])

        #     # ok = SqDiff[:,j] > (mean - (3 * stddev))
        #     # SqDiff[~ok,j] = mean

        #     # #step 2, values higher than 1 std from mean
        #     # # ok = SqDiff[:,j] < (mean + ( 3 * stddev))
        #     # # SqDiff[~ok,j] = mean

        #     meanSqDiff[j] = np.sum(SqDiff[:,j])

        #print("sum squared diff matrices: " + str(sumSqDiff))
        meanSumSquared = np.sum(meanSqDiff)

        return meanSumSquared 
    
    def returnTrajecInformation(self):

        self.jerkProfile = self.calcJerkOverTrajectory(self.states[0])
        self.accelProfile = self.calculateAccellerationOverTrajectory(self.states[0])


        return self.jerkProfile, self.accelProfile, self.states[0].copy(), self.controls[0].copy()

    def calculateAccellerationOverTrajectory(self, trajectoryStates):
        accel = np.zeros((self.trajecLength - 1, self.numStates))

        for i in range(self.trajecLength - 1):

            state1 = trajectoryStates[i,:].copy()
            state2 = trajectoryStates[i+1,:].copy()

            currentAccel = state2 - state1

            accel[i,:] = currentAccel

        return accel

    def calcJerkOverTrajectory(self, trajectoryStates):
        jerk = np.zeros((self.trajecLength - 2, self.numStates))

        for i in range(self.trajecLength - 2):

            state1 = trajectoryStates[i,:].copy()
            state2 = trajectoryStates[i+1,:].copy()
            state3 = trajectoryStates[i+2,:].copy()

            accel1 = state3 - state2
            accel2 = state1 - state1

            currentJerk = accel2 - accel1

            jerk[i,:] = currentJerk

        return jerk
    
    def keyPoints_setInterval(self, dynParameters):
        keyPoints = []
        keyPoints.append(0)

        minN = int(dynParameters[0])
        counter = 0

        for i in range(self.trajecLength - 1):
            counter += 1
            if counter >= minN:
                counter = 0
                keyPoints.append(i)

        keyPoints.append(self.trajecLength - 1)
        return keyPoints 

    def keyPoints_adaptiveJerk(self, trajectoryStates, dynParameters):
        keyPoints = []
        counterSinceLastEval = 0
        keyPoints.append(0)

        minN = int(dynParameters[0])
        maxN = int(dynParameters[1])
        velGradSensitivty = dynParameters[2]
        # temp
        velGradCubeSensitivity = 0.0002

        jerkProfile = self.calcJerkOverTrajectory(self.states[0])
        print(jerkProfile.shape)

        for i in range(len(jerkProfile)):

            if(counterSinceLastEval >= minN):
                for j in range(len(jerkProfile[i])):
                    if(jerkProfile[i,j] > velGradSensitivty):
                        keyPoints.append(i)
                        counterSinceLastEval = 0
            
            if(counterSinceLastEval >= maxN):
                keyPoints.append(i)
                counterSinceLastEval = 0

            counterSinceLastEval = counterSinceLastEval + 1

        keyPoints.append(self.trajecLength - 1)

        return keyPoints 

    def keyPoints_adaptiveAccel(self, trajectoryStates, dynParameters):
        keyPoints = []
        counterSinceLastEval = 0
        keyPoints.append(0)

        minN = int(dynParameters[0])
        maxN = int(dynParameters[1])
        velGradSensitivty = dynParameters[2]
        # temp
        velGradCubeSensitivity = 0.0002

        accelProfile = self.calculateAccellerationOverTrajectory(self.states[0])

        for i in range(len(accelProfile)):

            if(counterSinceLastEval >= minN):

                for j in range(len(accelProfile[i])):
                    if(accelProfile[i,j] > velGradSensitivty):
                        keyPoints.append(i)
                        counterSinceLastEval = 0
            
            if(counterSinceLastEval >= maxN):
                keyPoints.append(i)
                counterSinceLastEval = 0

            counterSinceLastEval = counterSinceLastEval + 1

        keyPoints.append(self.trajecLength - 1)

        return keyPoints  

    def keyPoints_iteratively(self, trajectoryStates, dynParameters):
        keyPoints = []

        startInterval = int(self.trajecLength / 2)
        numMaxBins = int((self.trajecLength / startInterval))

        for i in range(numMaxBins):
            binComplete = False
            startIndex = i * startInterval
            endIndex = (i + 1) * startInterval
            if(endIndex >= self.trajecLength):
                endIndex = self.trajecLength - 1
            listofIndicesCheck = []
            indexTuple = (startIndex, endIndex)
            listofIndicesCheck.append(indexTuple)
            subListIndices = []
            subListWithMidpoints = []

            while(not binComplete):

                allChecksComplete = True
                for j in range(len(listofIndicesCheck)):

                    approximationGood, midIndex = self.oneCheck(trajectoryStates, listofIndicesCheck[j])

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
                        keyPoints.append(subListWithMidpoints[k])

                    subListWithMidpoints = []

                listofIndicesCheck = subListIndices.copy()
                subListIndices = []

        keyPoints.sort()
        keyPoints = list(dict.fromkeys(keyPoints))

        return keyPoints
    
    def generateKeypoints(self, trajectoryStates, trajectoryControls, dynParameters):
        keyPoints = []

        keyPoints_setInterval = self.keyPoints_setInterval(dynParameters)
        keyPoints_adaptiveJerk = self.keyPoints_adaptiveJerk(trajectoryStates, dynParameters)
        keyPoints_adaptiveAccel = self.keyPoints_adaptiveAccel(trajectoryStates, dynParameters)
        keyPoints_iteratively = self.keyPoints_iteratively(trajectoryStates, dynParameters)

        max_length = max(len(keyPoints_setInterval), len(keyPoints_adaptiveJerk), len(keyPoints_adaptiveAccel), len(keyPoints_iteratively))

        # Extend the shorter lists with None values
        keyPoints_setInterval.extend([None] * (max_length - len(keyPoints_setInterval)))
        keyPoints_adaptiveJerk.extend([None] * (max_length - len(keyPoints_adaptiveJerk)))
        keyPoints_adaptiveAccel.extend([None] * (max_length - len(keyPoints_adaptiveAccel)))
        keyPoints_iteratively.extend([None] * (max_length - len(keyPoints_iteratively)))

        # keyPoints.append(keyPoints_setInterval)
        # keyPoints.append(keyPoints_adaptiveJerk)
        # keyPoints.append(keyPoints_adaptiveAccel)
        # keyPoints.append(keyPoints_iteratively)

        # Stack the keypoints into one array
        keyPoints = np.vstack((keyPoints_setInterval, keyPoints_adaptiveJerk, keyPoints_adaptiveAccel, keyPoints_iteratively))

        return keyPoints
    

    def newEvaluationNeeded(self, currentGrads, lastGrads, sensitivity, cubeSensitivity):
        newEvalNeeded = False

        for i in range(self.dof):
            # print("current grad: " + str(currentGrads[dof + i]))
            # print("last grad: " + str(lastGrads[dof + i]))
            velGradDiff = currentGrads[self.dof + i] - lastGrads[self.dof + i]
            # print(velGradDiff)

            if(i < 7):
                if(velGradDiff > sensitivity):
                    newEvalNeeded = True
                    #print("new eval needed, diff: " + str(velGradDiff))

                if(velGradDiff < -sensitivity):
                    newEvalNeeded = True
                    #print("new eval needed, diff: " + str(velGradDiff))

            else:
                if(velGradDiff > cubeSensitivity):
                    newEvalNeeded = True
                    #print("new eval needed, diff: " + str(velGradDiff))

                if(velGradDiff < -cubeSensitivity):
                    newEvalNeeded = True
                    #print("new eval needed, diff: " + str(velGradDiff))
            
        return newEvalNeeded
        
    def oneCheck(self, A_matrices, indexTuple):
        approximationGood = False

        startIndex = indexTuple[0]
        endIndex = indexTuple[1]

        midIndex = int((startIndex + endIndex) / 2)
        startVals = A_matrices[startIndex,:]
        endVals = A_matrices[endIndex,:]

        if((endIndex - startIndex) < 5):
            return True, midIndex

        trueMidVals = A_matrices[midIndex,:]
        diff = endVals - startVals
        linInterpMidVals = startVals + (diff/2)

        meanSqDiff = self.meansqDiffBetweenAMatrices(trueMidVals, linInterpMidVals)
        # sumsqDiff = self.sumsqDiffBetweenAMatrices(trueMidVals, linInterpMidVals)
        print("meanSqDiff: " + str(meanSqDiff))

        # 0.05 for reaching and pushing
        #~0.001 for pendulum
        if(meanSqDiff < 0.002):
            approximationGood = True

        return approximationGood, midIndex
    
    def sumsqDiffBetweenAMatrices(self, matrix1, matrix2):
        sumsqDiff = 0

        for i in range(len(matrix1)):
            sqDiff = (matrix1[i] - matrix2[i])**2
            if(sqDiff > 0.01):
                #ignore large values
                sqDiff = 0

            sumsqDiff = sumsqDiff + sqDiff

        return sumsqDiff

    def meansqDiffBetweenAMatrices(self, matrix1, matrix2):
        sumsqDiff = 0
        counter = 0
        counterSmallVals = 0

        for i in range(len(matrix1)):
            sqDiff = (matrix1[i] - matrix2[i])**2
            if(sqDiff < 0.000001):
                #ignore large values
                sqDiff = 0
                counterSmallVals += 1
            elif(sqDiff > 0.5):
                sqDiff = 0
            else:
                counter = counter + 1

            sumsqDiff = sumsqDiff + sqDiff

        if(counter == 0):
            sumsqDiff = 0
        else:
            sumsqDiff = sumsqDiff / counter
            
        print("counter: " + str(counter))
        print("counter small vals: " + str(counterSmallVals))
        

        return sumsqDiff

    
    def generateLinInterpolation(self, A_matrices, reEvaluationIndicies):
        sizeofAMatrix = len(A_matrices[0])
        linInterpolationData = np.zeros((self.trajecLength, sizeofAMatrix))

        #Drop any none values at end of list
        reEvaluationIndicies = [x for x in reEvaluationIndicies if x is not None]
        numBins = len(reEvaluationIndicies) - 1
        #print("num bins: " + str(numBins))
        stepsBetween = 0

        for i in range(numBins):
                
            startIndex = reEvaluationIndicies[i]
            startVals = A_matrices[startIndex,:]

            endIndex = reEvaluationIndicies[i + 1]
            endVals = A_matrices[endIndex,:]

            diff = endVals - startVals

            stepsBetween = endIndex - startIndex

            linInterpolationData[startIndex,:] = startVals

            for k in range(1, stepsBetween):
                linInterpolationData[startIndex + k,:] = startVals + (diff * (k/stepsBetween))

        
        linInterpolationData[len(linInterpolationData) - 1,:] = linInterpolationData[len(linInterpolationData) - 2,:]
        return linInterpolationData
    
    def generateQuadInterpolation(self, A_matrices, reEvaluationIndicies):
        sizeofMatrix = len(A_matrices[0])
        quadInterpolationData = np.zeros((self.trajecLength, sizeofMatrix))

        for i in range(len(reEvaluationIndicies) - 2):
            startIndex = reEvaluationIndicies[i]
            midIndex = reEvaluationIndicies[i + 1]
            endIndex = reEvaluationIndicies[i + 2]

            for j in range(sizeofMatrix):

                points = np.zeros((3, 2))
                point1 = np.array([A_matrices[startIndex, j], startIndex])
                point2 = np.array([A_matrices[midIndex, j], midIndex])
                point3 = np.array([A_matrices[endIndex, j], endIndex])

                points[0] = point1
                points[1] = point2
                points[2] = point3

                #solve for coefficients a, b, c

                x_matrix = np.zeros((3, 3))
                y_matrix = np.zeros((1, 3))

                y_matrix[0, 0] = points[0, 0]
                y_matrix[0, 1] = points[1, 0]
                y_matrix[0, 2] = points[2, 0]

                for k in range(3):
                    x_matrix[0, k] = points[k, 1] * points[k, 1]
                    x_matrix[1, k] = points[k, 1]
                    x_matrix[2, k] = 1

                x_inv = np.linalg.inv(x_matrix)

                abc = y_matrix @ x_inv

                quadInterpolationData[startIndex,j] = A_matrices[startIndex,j]

                counter = 0
                for k in range(startIndex, endIndex):
                    a = abc[0, 0]
                    b = abc[0, 1]
                    c = abc[0, 2]

                    nextVal = (a * k * k) + (b * k) + c
                    quadInterpolationData[startIndex + counter, j] = nextVal
                    counter = counter + 1

        quadInterpolationData[len(quadInterpolationData) - 1,:] = quadInterpolationData[len(quadInterpolationData) - 2,:]

        return quadInterpolationData
    
    def generateCubicInterpolation(self, A_matrices, reEvaluationIndicies):
        sizeofMatrix = len(A_matrices[0])
        quadInterpolationData = np.zeros((self.trajecLength, sizeofMatrix))

        for i in range(len(reEvaluationIndicies) - 3):
            startIndex = reEvaluationIndicies[i]
            midIndex1 = reEvaluationIndicies[i + 1]
            midIndex2 = reEvaluationIndicies[i + 2]
            endIndex = reEvaluationIndicies[i + 3]

            for j in range(sizeofMatrix):

                points = np.zeros((4, 2))
                point1 = np.array([A_matrices[startIndex, j], startIndex])
                point2 = np.array([A_matrices[midIndex1, j], midIndex1])
                point3 = np.array([A_matrices[midIndex2, j], midIndex2])
                point4 = np.array([A_matrices[endIndex, j], endIndex])

                points[0] = point1
                points[1] = point2
                points[2] = point3
                points[3] = point4

                #solve for coefficients a, b, c

                x_matrix = np.zeros((4, 4))
                y_matrix = np.zeros((1, 4))

                y_matrix[0, 0] = points[0, 0]
                y_matrix[0, 1] = points[1, 0]
                y_matrix[0, 2] = points[2, 0]
                y_matrix[0, 3] = points[3, 0]

                for k in range(4):
                    x_matrix[0, k] = points[k, 1] * points[k, 1] * points[k, 1]
                    x_matrix[1, k] = points[k, 1] * points[k, 1]
                    x_matrix[2, k] = points[k, 1]
                    x_matrix[3, k] = 1

                x_inv = np.linalg.inv(x_matrix)

                abcd = y_matrix @ x_inv

                quadInterpolationData[startIndex,j] = A_matrices[startIndex,j]

                counter = 0
                for k in range(startIndex, endIndex):
                    a = abcd[0, 0]
                    b = abcd[0, 1]
                    c = abcd[0, 2]
                    d = abcd[0, 3]

                    nextVal = (a * k * k * k) + (b * k * k) + (c * k) + d
                    quadInterpolationData[startIndex + counter, j] = nextVal
                    counter = counter + 1

        quadInterpolationData[len(quadInterpolationData) - 1,:] = quadInterpolationData[len(quadInterpolationData) - 2,:]

        return quadInterpolationData
    
    def butter_lowpass_filter(self, data, cutoff, nyq, order):
        normal_cutoff = cutoff / nyq
        # Get the filter coefficients 
        b, a = butter(order, normal_cutoff, btype='low', analog=False)
        y = filtfilt(b, a, data)
        return y

def testFilter():
    pass

def filterArray(unfiltered):
    PI = 3.1415
    yn1 = unfiltered[0]
    xn1 = unfiltered[0]

    filtered = []

    for i in range(len(unfiltered)):

        xn = unfiltered[i]
        yn = 0.2283*yn1 + 0.3859*xn + 0.3859*xn1

        xn1 = xn
        yn1 = yn

        filtered.append(yn)

    plt.plot(filtered)
    plt.plot(unfiltered)
    plt.show()

def ICRATemp():
    myInterp = interpolator(1, 1)

    dynParams = [5, 200, 0.0005]

    trueTrajec, interpolatedTrajec, unfilteredTrajec, errors, reEvaluationIndices, iterativeKeyPoints = myInterp.interpolateTrajectory(0, dynParams)
            

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

if __name__ == "__main__":
    ICRATemp()

    # myInterp = interpolator(0, 2)

    # # Filter requirements.
    # T = 5.0         # Sample Period
    # fs = 100      # sample rate, Hz
    # cutoff = 1      # desired cutoff frequency of the filter, Hz ,      slightly higher than actual 1.2 Hz
    # nyq = 0.5 * fs  # Nyquist Frequency
    # order = 2       # sin wave can be approx represented as quadratic
    # n = int(T * fs) # total number of samples

    # index = 1
    # for i in range(10):
    #     filterArray(myInterp.testTrajectories[0][:,index + i])

    # filterArray(myInterp.testTrajectories[0][:,index])

    # filteredData = myInterp.butter_lowpass_filter(myInterp.testTrajectories[0][:,index], cutoff, fs, order)

    # plt.plot(myInterp.testTrajectories[0][:,index])
    # plt.plot(filteredData)
    # plt.show()



