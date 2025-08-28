protocol TaskExecution v1.0.0
requires {
    authentication: "jwt"
    encryption: "aes256"
    persistence: "required"
}

definitions {
    type TaskData {
        id: String
        description: String
        priority: PriorityLevel = "MEDIUM"
        deadline: Timestamp
        resources: List<String>
    }

    type ResultData {
        taskId: String
        status: String
        output: Map
        metrics: Map
        timestamp: Timestamp
    }

    message TaskAssignment {
        sender: Broker
        receiver: Agent
        payload: TaskData
        priority: HIGH
        timeout: 30s
    }

    role Broker {
        capabilities: ["load-balancing", "routing"]
        states: [INIT, ACTIVE, WAITING]
    }

    role Agent {
        capabilities: ["task-execution", "monitoring"]
        states: [INIT, ACTIVE, COMPLETED]
    }
}

flow {
    stage TaskInitiation {
        preconditions: [
            authenticated(sender),
            hasCapacity(receiver)
        ]
        actions: [
            validateTask(payload),
            assignResources(),
            notifyParticipants()
        ]
        postconditions: [
            taskAssigned(),
            resourcesAllocated()
        ]
        error: retry(max=3)
    }

    transaction ExecuteTask {
        atomic: true
        participants: [Broker, Agent]
        steps: [
            validateInput(),
            processTask(),
            validateOutput()
        ]
        compensation: [
            releaseResources(),
            notifyFailure()
        ]
    }
}
