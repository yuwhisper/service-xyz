-- Ozon shipment registration table for POST /service/zyx/ozon/fahuo
-- Run on server MySQL (database: zyx)

CREATE TABLE IF NOT EXISTS `ods_ozon_装箱发货登记表` (
    `唯一ID` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `内部订单号` VARCHAR(128) DEFAULT NULL,
    `发货人` VARCHAR(64) DEFAULT NULL,
    `运营发货日期` DATE DEFAULT NULL,
    `店铺` VARCHAR(32) DEFAULT NULL,
    `集群` VARCHAR(128) DEFAULT NULL,
    `发货方式` VARCHAR(16) DEFAULT NULL COMMENT '直发 / 中转',
    `批次号` VARCHAR(64) DEFAULT NULL,
    `SKU` VARCHAR(64) DEFAULT NULL,
    `总箱数` INT DEFAULT NULL,
    `单箱数量` INT DEFAULT NULL,
    `单箱重量` DECIMAL(10, 3) DEFAULT NULL,
    `箱规长(cm)` DECIMAL(10, 2) DEFAULT NULL,
    `宽` DECIMAL(10, 2) DEFAULT NULL,
    `高` DECIMAL(10, 2) DEFAULT NULL,
    `中文名称` VARCHAR(255) DEFAULT NULL,
    `材料` VARCHAR(255) DEFAULT NULL,
    `发货状态` VARCHAR(32) DEFAULT NULL,
    KEY `idx_ship_date_status` (`运营发货日期`, `发货状态`),
    KEY `idx_shop_batch` (`店铺`, `批次号`, `运营发货日期`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
