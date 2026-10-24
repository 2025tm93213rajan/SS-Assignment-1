# Domain Alternatives, 5-6 Service Architectures & Minikube Strategy
## Scalable Services (SEZG583) - Assignment 1 & 2 Blueprint

---

## 1. Minikube & Docker Clarification (Assignment 1 vs. Assignment 2)

### What the Assignment Specification Dictates:
> **"Link to Assignment 2: The same application is containerised and deployed on Docker and Minikube in Assignment 2. Design it with that in mind."**

* **Assignment 1 (Current - 13 Marks)**:
  - Focuses on **Application Architecture, Microservice Decomposition, Business Logic, REST APIs, Concurrency Control, Idempotency, and Failure Resiliency (Saga/Broker)**.
  - Requires each service to have its own folder, dependency manifest, independent database, environment configuration, and containerization via **Docker** and **Docker Compose**.
* **Assignment 2 (Next Phase - 7 Marks)**:
  - Takes this exact application and deploys it onto a Kubernetes cluster (**Minikube**), configuring Pods, ReplicaSets, Services, ClusterIP, NodePort/Ingress, ConfigMaps, Secrets, and PersistentVolumeClaims.
* **Our Forward-Compatible Design Strategy**:
  - We build complete, standalone **Dockerfiles** for every service and data store now.
  - We also pre-scaffold the **Kubernetes Manifests (`k8s/`)** (Deployments, Services, ConfigMaps) right here in Assignment 1. This guarantees that your Assignment 1 code is 100% verified to work on Docker and will deploy directly to Minikube in Assignment 2 with zero refactoring!

---

## 2. Expanded 5-Service Architecture in "SeatLock"

The platform expands to an **Omnichannel Reservation System** (IRCTC Railway Tatkal, Stadium Concert Passes, Intercity Transit):
1. `inventory-service` (Seats, Berths, Quotas)
2. `booking-service` (Saga Orchestration, Order Lifecycle)
3. `payment-service` (Mock Gateway, Idempotency Ledger)
4. `ticketing-service` (PNR Generation, Seat Allocation, Barcodes)
5. `notification-service` (RabbitMQ Consumer, Delivery Audit)
*(Plus API Gateway & Next.js Frontend Cockpit)*
